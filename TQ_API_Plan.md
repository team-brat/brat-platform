# TQ Page - Inspection Records: API Usage Plan

---

## Overview

This API plan defines the frontend-backend integration for the TQ (Inspection Records) section of the WMS project.

**Scope:**
- Allow users to search inspection records by filters.
- Display all available inspection records on initial page load.

**Notes:**
- Sample/mock data will be used initially.
- Real database connection will be configured later.

---

## 1. Search Inspection Records

| Item | Description |
|:---|:---|
| **API Endpoint** | POST `/search-inspection-records` |
| **Trigger** | When user clicks the Search button |
| **Request Payload** |
```json
{
  "supplier_name": "string (optional)",
  "supplier_id": "string (optional)",
  "sku_name": "string (optional)",
  "sku_id": "string (optional)",
  "serial_or_barcode": "string (optional)",
  "inspection_date_range": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  }
}
