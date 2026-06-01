# shared/utilities/agriculture_utils/geometry_utils.py
"""Geometry utilities for agriculture calculations"""

import math
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Point:
    """2D point representation"""
    lat: float
    lon: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lon)


@dataclass
class BoundingBox:
    """Geographic bounding box"""
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    
    @property
    def width(self) -> float:
        return self.max_lon - self.min_lon
    
    @property
    def height(self) -> float:
        return self.max_lat - self.min_lat
    
    @property
    def center(self) -> Point:
        return Point(
            (self.min_lat + self.max_lat) / 2,
            (self.min_lon + self.max_lon) / 2
        )


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unit: str = "meters"
) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
        unit: Output unit (meters, kilometers, miles)
        
    Returns:
        Distance in specified unit
    """
    
    # Earth radius in meters
    R = 6371000
    
    # Convert to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance_meters = R * c
    
    # Convert to requested unit
    if unit == "kilometers":
        return distance_meters / 1000
    elif unit == "miles":
        return distance_meters / 1609.34
    else:  # meters
        return distance_meters


def calculate_field_area(
    vertices: List[Tuple[float, float]],
    unit: str = "hectares"
) -> float:
    """
    Calculate area of a polygon defined by vertices
    
    Args:
        vertices: List of (lat, lon) vertices in order
        unit: Output unit (hectares, acres, square_meters)
        
    Returns:
        Area in specified unit
    """
    
    if len(vertices) < 3:
        return 0.0
    
    # Calculate area using Shoelace formula
    area_sqm = 0.0
    n = len(vertices)
    
    for i in range(n):
        j = (i + 1) % n
        
        # Convert to meters using approximate conversion
        lat1, lon1 = vertices[i]
        lat2, lon2 = vertices[j]
        
        # Approximate distance in meters
        dx = haversine_distance(lat1, lon1, lat1, lon2)
        dy = haversine_distance(lat1, lon1, lat2, lon1)
        
        area_sqm += dx * dy
    
    area_sqm = abs(area_sqm) / 2
    
    # Convert to requested unit
    if unit == "hectares":
        return area_sqm / 10000
    elif unit == "acres":
        return area_sqm / 4046.86
    else:  # square_meters
        return area_sqm


def calculate_field_perimeter(
    vertices: List[Tuple[float, float]],
    unit: str = "meters"
) -> float:
    """
    Calculate perimeter of a polygon
    
    Args:
        vertices: List of (lat, lon) vertices in order
        unit: Output unit (meters, kilometers)
        
    Returns:
        Perimeter in specified unit
    """
    
    if len(vertices) < 3:
        return 0.0
    
    perimeter = 0.0
    n = len(vertices)
    
    for i in range(n):
        j = (i + 1) % n
        lat1, lon1 = vertices[i]
        lat2, lon2 = vertices[j]
        
        perimeter += haversine_distance(lat1, lon1, lat2, lon2)
    
    if unit == "kilometers":
        return perimeter / 1000
    else:
        return perimeter


def create_grid_over_field(
    field_vertices: List[Tuple[float, float]],
    grid_cell_size_meters: float = 10
) -> List[BoundingBox]:
    """
    Create a grid of cells over a field
    
    Args:
        field_vertices: Field boundary vertices
        grid_cell_size_meters: Size of each grid cell in meters
        
    Returns:
        List of bounding boxes for each grid cell
    """
    
    # Find field bounds
    min_lat = min(v[0] for v in field_vertices)
    max_lat = max(v[0] for v in field_vertices)
    min_lon = min(v[1] for v in field_vertices)
    max_lon = max(v[1] for v in field_vertices)
    
    # Convert grid size to degrees (approximate)
    lat_center = (min_lat + max_lat) / 2
    lon_center = (min_lon + max_lon) / 2
    
    # One degree of latitude is approximately 111,000 meters
    lat_step = grid_cell_size_meters / 111000
    
    # One degree of longitude varies with latitude
    lon_step = grid_cell_size_meters / (111000 * math.cos(math.radians(lat_center)))
    
    cells = []
    
    lat = min_lat
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            cell = BoundingBox(
                min_lat=lat,
                min_lon=lon,
                max_lat=min(lat + lat_step, max_lat),
                max_lon=min(lon + lon_step, max_lon)
            )
            
            # Check if cell center is within field (simplified)
            if point_in_polygon(cell.center.to_tuple(), field_vertices):
                cells.append(cell)
            
            lon += lon_step
        lat += lat_step
    
    return cells


def point_in_polygon(
    point: Tuple[float, float],
    polygon: List[Tuple[float, float]]
) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm
    
    Args:
        point: (lat, lon) point
        polygon: List of (lat, lon) vertices
        
    Returns:
        True if point is inside polygon
    """
    
    x, y = point
    inside = False
    
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        
        # Check if point is on horizontal edge
        if y == y1 == y2 and min(x1, x2) <= x <= max(x1, x2):
            return True
        
        # Check if ray crosses edge
        if ((y1 > y) != (y2 > y)) and \
           (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    
    return inside


def calculate_optimal_route(
    points: List[Tuple[float, float]],
    start_point: Optional[Tuple[float, float]] = None
) -> List[Tuple[float, float]]:
    """
    Calculate optimal route to visit all points (simplified TSP)
    
    Args:
        points: List of points to visit
        start_point: Starting point (defaults to first point)
        
    Returns:
        Optimal route order
    """
    
    if not points:
        return []
    
    if start_point is None:
        start_point = points[0]
    
    unvisited = points.copy()
    route = [start_point]
    
    if start_point in unvisited:
        unvisited.remove(start_point)
    
    current = start_point
    
    while unvisited:
        # Find nearest unvisited point
        nearest = min(
            unvisited,
            key=lambda p: haversine_distance(
                current[0], current[1], p[0], p[1]
            )
        )
        
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    
    return route


def estimate_yield_from_area(
    area_hectares: float,
    crop_type: str,
    expected_yield_kg_per_hectare: Optional[float] = None
) -> Dict[str, Any]:
    """
    Estimate crop yield based on area
    
    Args:
        area_hectares: Field area in hectares
        crop_type: Type of crop
        expected_yield_kg_per_hectare: Custom yield expectation
        
    Returns:
        Yield estimation dictionary
    """
    
    # Default yields (kg per hectare)
    default_yields = {
        "maize": 3000,
        "tomato": 20000,
        "cassava": 15000,
        "wheat": 3500,
        "rice": 4000
    }
    
    yield_per_hectare = expected_yield_kg_per_hectare or default_yields.get(
        crop_type.lower(), 5000
    )
    
    total_yield_kg = area_hectares * yield_per_hectare
    total_yield_tons = total_yield_kg / 1000
    
    return {
        "area_hectares": area_hectares,
        "crop_type": crop_type,
        "yield_per_hectare_kg": yield_per_hectare,
        "total_yield_kg": total_yield_kg,
        "total_yield_tons": total_yield_tons,
        "estimated_value_usd": total_yield_kg * 0.5  # Rough estimate
    }


def get_bounding_box_from_points(
    points: List[Tuple[float, float]],
    padding_meters: float = 0
) -> BoundingBox:
    """
    Get bounding box that contains all points
    
    Args:
        points: List of points
        padding_meters: Padding to add around bounding box in meters
        
    Returns:
        Bounding box
    """
    
    if not points:
        return BoundingBox(0, 0, 0, 0)
    
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    
    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)
    
    # Add padding if specified
    if padding_meters > 0:
        lat_center = (min_lat + max_lat) / 2
        lat_padding = padding_meters / 111000
        lon_padding = padding_meters / (111000 * math.cos(math.radians(lat_center)))
        
        min_lat -= lat_padding
        max_lat += lat_padding
        min_lon -= lon_padding
        max_lon += lon_padding
    
    return BoundingBox(min_lat, min_lon, max_lat, max_lon)