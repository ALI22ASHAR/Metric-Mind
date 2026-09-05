import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.analytics.duckdb_engine import duckdb_engine
from app.analytics.metric_registry import metric_capability_analyzer
from app.schemas.analytics import DimensionFilter
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)

# Standard regional geographic coordinates and bounds for interactive map representation
REGION_COORDINATES = {
    "north america": {"lat": 40.0, "lng": -100.0, "code": "NA", "zoom": 3},
    "europe": {"lat": 50.0, "lng": 15.0, "code": "EU", "zoom": 4},
    "asia pacific": {"lat": 20.0, "lng": 105.0, "code": "APAC", "zoom": 3},
    "asia": {"lat": 30.0, "lng": 100.0, "code": "AS", "zoom": 3},
    "latin america": {"lat": -15.0, "lng": -60.0, "code": "LATAM", "zoom": 3},
    "south america": {"lat": -15.0, "lng": -60.0, "code": "SA", "zoom": 3},
    "middle east & africa": {"lat": 15.0, "lng": 35.0, "code": "MEA", "zoom": 3},
    "africa": {"lat": 5.0, "lng": 25.0, "code": "AF", "zoom": 3},
    "united states": {"lat": 37.09, "lng": -95.71, "code": "USA", "zoom": 4},
    "usa": {"lat": 37.09, "lng": -95.71, "code": "USA", "zoom": 4},
    "canada": {"lat": 56.13, "lng": -106.34, "code": "CAN", "zoom": 3},
    "united kingdom": {"lat": 55.37, "lng": -3.43, "code": "GBR", "zoom": 5},
    "uk": {"lat": 55.37, "lng": -3.43, "code": "GBR", "zoom": 5},
    "germany": {"lat": 51.16, "lng": 10.45, "code": "DEU", "zoom": 5},
    "france": {"lat": 46.22, "lng": 2.21, "code": "FRA", "zoom": 5},
    "australia": {"lat": -25.27, "lng": 133.77, "code": "AUS", "zoom": 4},
    "japan": {"lat": 36.20, "lng": 138.25, "code": "JPN", "zoom": 5},
    "china": {"lat": 35.86, "lng": 104.19, "code": "CHN", "zoom": 4},
    "india": {"lat": 20.59, "lng": 78.96, "code": "IND", "zoom": 4},
    "brazil": {"lat": -14.23, "lng": -51.92, "code": "BRA", "zoom": 4},
}

CITY_COORDINATES = {
    "chicago": {"lat": 41.8781, "lng": -87.6298, "code": "CHI"},
    "new york": {"lat": 40.7128, "lng": -74.0060, "code": "NYC"},
    "new york city": {"lat": 40.7128, "lng": -74.0060, "code": "NYC"},
    "dallas": {"lat": 32.7767, "lng": -96.7970, "code": "DAL"},
    "london": {"lat": 51.5072, "lng": -0.1276, "code": "LON"},
    "paris": {"lat": 48.8566, "lng": 2.3522, "code": "PAR"},
    "berlin": {"lat": 52.5200, "lng": 13.4050, "code": "BER"},
    "tokyo": {"lat": 35.6762, "lng": 139.6503, "code": "TYO"},
    "sydney": {"lat": -33.8688, "lng": 151.2093, "code": "SYD"},
}


class GeoFeatureMetric(BaseModel):
    region_name: str
    region_code: str
    latitude: float
    longitude: float
    metric_id: str
    metric_value: float
    formatted_value: str
    share_percentage: float
    order_count: int


class GeoBreakdownResponse(BaseModel):
    dataset_id: str
    geo_column: str
    metric_id: str
    total_metric_value: float
    features: List[GeoFeatureMetric] = []
    has_geographic_data: bool = True


class GeoEngine:
    """
    Computes geospatial analytics and regional choropleth distributions for map visualizations.
    """

    @classmethod
    def identify_geo_column(
        cls,
        columns: List[str],
        semantic_model: SemanticModelSchema,
    ) -> Optional[str]:
        """
        Detects primary geographic column (e.g. Country, Region, State, City).
        """
        geo_names = ["country", "region", "state", "province", "territory", "nation", "market", "city"]
        
        # Prefer the most detailed geographic level available for a useful map.
        level_priority = ("city", "state", "province", "region", "country", "market", "territory", "nation")
        candidate_dims = [dim for dim in (semantic_model.dimensions or []) if any(g in dim.lower() for g in geo_names)]
        for level in level_priority:
            for dim in candidate_dims:
                if level in dim.lower():
                    return dim

        # 2. Check all columns
        candidate_cols = [col for col in columns if any(g in col.lower() for g in geo_names)]
        for level in level_priority:
            for col in candidate_cols:
                if level in col.lower():
                    return col

        return None

    @classmethod
    def identify_coordinate_columns(cls, columns: List[str]) -> tuple[Optional[str], Optional[str]]:
        latitude_names = {"lat", "latitude", "geo_lat", "y"}
        longitude_names = {"lng", "lon", "long", "longitude", "geo_lng", "geo_lon", "x"}
        latitude = next((column for column in columns if column.lower() in latitude_names), None)
        longitude = next((column for column in columns if column.lower() in longitude_names), None)
        return latitude, longitude

    @classmethod
    def compute_geo_breakdown(
        cls,
        dataset_id: str,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        columns: List[str],
        metric_id: str = "total_revenue",
        filters: Optional[List[DimensionFilter]] = None,
    ) -> GeoBreakdownResponse:
        """
        Aggregates KPI values per geographical location for map widgets.
        """
        geo_col = cls.identify_geo_column(columns, semantic_model)
        if not geo_col:
            return GeoBreakdownResponse(
                dataset_id=dataset_id,
                geo_column="",
                metric_id=metric_id,
                total_metric_value=0.0,
                features=[],
                has_geographic_data=False,
            )

        bd = duckdb_engine.compute_breakdown(
            parquet_path=parquet_path,
            dimension=geo_col,
            metric_ids=[metric_id],
            semantic_model=semantic_model,
            filters=filters,
            limit=50,
            sort_by=metric_id,
            ascending=False,
        )

        rows = bd.rows
        latitude_col, longitude_col = cls.identify_coordinate_columns(columns)
        if latitude_col and longitude_col:
            # Replace fallback coordinates with the data's actual geographic centers.
            normalized_path = Path(parquet_path).as_posix()
            con = duckdb_engine.get_connection()
            try:
                coordinate_rows = con.execute(
                    f'''SELECT "{geo_col}" AS location_name,
                               AVG("{latitude_col}") AS latitude,
                               AVG("{longitude_col}") AS longitude
                        FROM '{normalized_path}'
                        WHERE "{latitude_col}" IS NOT NULL AND "{longitude_col}" IS NOT NULL
                        GROUP BY "{geo_col}"'''
                ).pl().to_dicts()
                coordinates = {str(row["location_name"]): row for row in coordinate_rows}
            except Exception as exc:
                logger.warning("Coordinate column lookup failed: %s", exc)
                coordinates = {}
            finally:
                con.close()
        else:
            coordinates = {}
        total_val = float(sum(r.get(metric_id, 0) or 0 for r in rows))
        features: List[GeoFeatureMetric] = []

        for r in rows:
            name = str(r.get("dimension_value", "Unknown"))
            val = float(r.get(metric_id, 0) or 0)
            share = round((val / total_val * 100.0), 1) if total_val > 0 else 0.0

            name_key = name.lower().strip()
            geo_info = coordinates.get(name, {}) or CITY_COORDINATES.get(name_key) or REGION_COORDINATES.get(
                name_key,
                {"lat": 20.0, "lng": 0.0, "code": name[:3].upper()},
            )

            fmt = f"${val:,.2f}" if "rev" in metric_id or "profit" in metric_id or "price" in metric_id else f"{val:,.0f}"

            features.append(
                GeoFeatureMetric(
                    region_name=name,
                    region_code=geo_info.get("code", name[:3].upper()),
                    latitude=geo_info.get("latitude", geo_info.get("lat", 0.0)),
                    longitude=geo_info.get("longitude", geo_info.get("lng", 0.0)),
                    metric_id=metric_id,
                    metric_value=val,
                    formatted_value=fmt,
                    share_percentage=share,
                    order_count=int(r.get("_row_count", 1) or 1),
                )
            )

        return GeoBreakdownResponse(
            dataset_id=dataset_id,
            geo_column=geo_col,
            metric_id=metric_id,
            total_metric_value=total_val,
            features=features,
            has_geographic_data=True,
        )


geo_engine = GeoEngine()
