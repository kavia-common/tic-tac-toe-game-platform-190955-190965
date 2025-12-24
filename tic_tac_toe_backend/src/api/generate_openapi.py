import json
import os

from src.api.main import app

"""
Utility script to write the current FastAPI app's OpenAPI schema to interfaces/openapi.json.
Run this after modifying routes to keep the interface spec up-to-date.
"""

def main():
    # Get the OpenAPI schema
    openapi_schema = app.openapi()

    # Write to file
    output_dir = "interfaces"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "openapi.json")

    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"OpenAPI schema written to {output_path}")

if __name__ == "__main__":
    main()
