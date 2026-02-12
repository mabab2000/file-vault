from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from supabase import create_client
from dotenv import load_dotenv
import os
import io
import mimetypes


load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY in environment or .env")

# Primary client (anon/publishable key) and optional admin client (service_role key)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_client = None
if SUPABASE_SERVICE_KEY:
    admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

BUCKET = "files"
EXPIRES_DEFAULT = 3600

app = FastAPI(title="Supabase Files API")


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Upload a file (uses uploaded filename) and return only `message` and `preview_url`."""
    contents = await file.read()
    remote = file.filename
    # Determine content type for the upload so previews render correctly
    ct = getattr(file, "content_type", None) or mimetypes.guess_type(remote)[0] or "application/octet-stream"

    client = admin_client or supabase
    try:
        # include content-type metadata on upload to ensure browsers can preview PDFs
        resp = client.storage.from_(BUCKET).upload(remote, contents, {"content-type": ct})
    except Exception as e:
        msg = str(e)
        # Permission / RLS error
        if "row-level security" in msg or "Unauthorized" in msg or "403" in msg:
            raise HTTPException(status_code=403, detail={
                "error": "upload_failed",
                "message": "Upload blocked by Supabase storage policy (403).",
                "action": "Provide SUPABASE_SERVICE_KEY (service_role) to the server or configure the bucket to allow public uploads."
            })

        # Duplicate resource: return existing file's preview URL instead of failing
        if "Duplicate" in msg or "already exists" in msg or "409" in msg:
            url_client = admin_client or supabase
            try:
                signed = url_client.storage.from_(BUCKET).create_signed_url(remote, EXPIRES_DEFAULT)
                if isinstance(signed, dict):
                    preview_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("publicURL") or signed.get("public_url")
                else:
                    preview_url = signed
            except Exception:
                preview_url = None

            return JSONResponse({"message": "already_exists", "preview_url": preview_url})

        raise HTTPException(status_code=500, detail=msg)

    # Create a signed preview URL using the admin client if available, otherwise try anon
    url_client = admin_client or supabase
    try:
        signed = url_client.storage.from_(BUCKET).create_signed_url(remote, EXPIRES_DEFAULT)
        if isinstance(signed, dict):
            preview_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("publicURL") or signed.get("public_url")
        else:
            preview_url = signed
    except Exception:
        preview_url = None
    # Build a server download URL for convenience
    try:
        base = str(request.base_url)
    except Exception:
        base = "/"

    download_url = f"{base}download?path={remote}"

    return JSONResponse({"message": "uploaded", "path": remote, "preview_url": preview_url, "download_url": download_url})





@app.get("/download")
def download(path: str):
    try:
        data = supabase.storage.from_(BUCKET).download(path)

        # Determine media type for response
        mime_type, _ = mimetypes.guess_type(path)
        media_type = mime_type or "application/octet-stream"

        if isinstance(data, (bytes, bytearray)):
            headers = {"Content-Disposition": f'attachment; filename="{os.path.basename(path)}"'}
            return StreamingResponse(io.BytesIO(data), media_type=media_type, headers=headers)

        # If client returns a file-like, stream it and set download header
        headers = {"Content-Disposition": f'attachment; filename="{os.path.basename(path)}"'}
        return StreamingResponse(data, media_type=media_type, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/preview")
def preview(path: str):
    """Return a signed preview URL for a file path in the Supabase bucket."""
    try:
        url_client = admin_client or supabase
        signed = url_client.storage.from_(BUCKET).create_signed_url(path, EXPIRES_DEFAULT)
        if isinstance(signed, dict):
            preview_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("publicURL") or signed.get("public_url")
        else:
            preview_url = signed
        return JSONResponse({"preview_url": preview_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download_link")
def download_link(path: str):
    """Return a signed download URL for a file path in the Supabase bucket."""
    try:
        url_client = admin_client or supabase
        signed = url_client.storage.from_(BUCKET).create_signed_url(path, EXPIRES_DEFAULT)
        if isinstance(signed, dict):
            download_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("publicURL") or signed.get("public_url")
        else:
            download_url = signed
        return JSONResponse({"download_url": download_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete")
def delete(path: str):
    try:
        resp = supabase.storage.from_(BUCKET).remove([path])
        return JSONResponse({"status": "ok", "result": resp})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
