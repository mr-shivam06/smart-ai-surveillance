"""
=============================================================
  File : backend/app/api/routes_vehicles.py
  Purpose : Vehicle intelligence endpoints

  Endpoints:
    GET  /vehicles              → all known vehicles
    GET  /vehicles/search       → search by color + shape
    GET  /vehicles/{global_id}  → one vehicle's full info
=============================================================
"""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.core.security import get_current_user
from app.schemas.schemas import VehicleOut

router = APIRouter()


@router.get("", response_model=List[VehicleOut])
def list_vehicles(
    limit        : int  = Query(100, ge=1, le=500),
    current_user : dict = Depends(get_current_user),
):
    """All vehicles seen since system start."""
    from app.vehicle_analysis import VehicleAnalyzer
    registry = VehicleAnalyzer.get_registry()
    results  = registry.search()[:limit]
    return results


@router.get("/search", response_model=List[VehicleOut])
def search_vehicles(
    color        : Optional[str] = Query(None),
    shape_type   : Optional[str] = Query(None),
    current_user : dict          = Depends(get_current_user),
):
    """
    Search vehicles by color and/or shape type.

    Examples:
      GET /vehicles/search?color=red
      GET /vehicles/search?shape_type=sedan
      GET /vehicles/search?color=white&shape_type=van/truck
    """
    from app.vehicle_analysis import VehicleAnalyzer
    return VehicleAnalyzer.search(
        color      = color      or "",
        shape_type = shape_type or "",
    )


@router.get("/{global_id}")
def get_vehicle(
    global_id    : str,
    current_user : dict = Depends(get_current_user),
):
    """Full info for one vehicle by its global ID."""
    from app.vehicle_analysis import VehicleAnalyzer
    info = VehicleAnalyzer.get_registry().get(global_id)
    if not info:
        from fastapi import HTTPException
        raise HTTPException(404, f"Vehicle {global_id} not found")
    return info.to_dict()