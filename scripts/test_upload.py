import httpx
import asyncio
import os

async def test_upload():
    url = "http://localhost:8000/v1/documents"
    file_path = "test_doc.txt"
    
    with open(file_path, "w") as f:
        f.write("This is a test document for Cogniflow Phase 2.")

    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": ("test_doc.txt", f, "text/plain")}
            try:
                response = await client.post(url, files=files)
                print(f"Status: {response.status_code}")
                print(f"Response: {response.json()}")
            except Exception as e:
                print(f"Error: {e}")
    
    os.remove(file_path)

if __name__ == "__main__":
    asyncio.run(test_upload())
