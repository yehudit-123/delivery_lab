from typing import Optional
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

# מבנה הנתונים בזיכרון
deliveries: dict[int, dict] = {}
next_id: int = 1

# סדר הסטטוסים המורשה
STATUS_ORDER = ["created", "in_transit", "delivered"]


# טיפול בשגיאות HTTP כדי להחזיר {"error": ...} במקום {"detail": ...}
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)}
    )


# טיפול בשגיאות ולידציה - החזרת 400 במקום 422
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid request body"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/deliveries", status_code=status.HTTP_201_CREATED)
async def create_delivery(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Request body must be valid JSON"}
        )

    if not isinstance(data, dict):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Request body must be a JSON object"}
        )

    recipient = data.get("recipient")
    address = data.get("address")

    if not isinstance(recipient, str) or not recipient.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Recipient must be a non-empty string"}
        )

    if not isinstance(address, str) or not address.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Address must be a non-empty string"}
        )

    global next_id
    delivery_id = next_id
    next_id += 1

    delivery = {
        "id": delivery_id,
        "recipient": recipient,
        "address": address,
        "status": "created"
    }
    deliveries[delivery_id] = delivery
    return delivery
    
    
@app.get("/deliveries")
def list_deliveries(status: Optional[str] = None):
    if status is not None:
        if status not in STATUS_ORDER:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown status: {status}"}
            )
        return [d for d in deliveries.values() if d["status"] == status]
    return list(deliveries.values())
    
    
@app.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int):
    if delivery_id not in deliveries:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Delivery not found"}
        )
    return deliveries[delivery_id]


@app.patch("/deliveries/{delivery_id}/status")
async def update_status(delivery_id: int, request: Request):
    if delivery_id not in deliveries:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Delivery not found"}
        )

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Request body must be valid JSON"}
        )

    if not isinstance(data, dict) or "status" not in data:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Status field is required"}
        )

    new_status = data.get("status")
    if new_status not in STATUS_ORDER:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid status: {new_status}"}
        )

    current_status = deliveries[delivery_id]["status"]
    current_idx = STATUS_ORDER.index(current_status)
    new_idx = STATUS_ORDER.index(new_status)

    # מותר להתקדם אך ורק צעד אחד קדימה
    if new_idx != current_idx + 1:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": f"Cannot transition from {current_status} to {new_status}"}
        )

    deliveries[delivery_id]["status"] = new_status
    return deliveries[delivery_id]


@app.delete("/deliveries/{delivery_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_delivery(delivery_id: int):
    if delivery_id not in deliveries:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Delivery not found"}
        )

    if deliveries[delivery_id]["status"] != "created":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Cannot delete delivery that is not in created status"}
        )

    del deliveries[delivery_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)