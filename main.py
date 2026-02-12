from supabase import create_client
from dotenv import load_dotenv
import os
import argparse


def upload_file(local_path: str, remote_path: str) -> None:
	load_dotenv()
	url = os.environ.get("SUPABASE_URL")
	key = os.environ.get("SUPABASE_KEY")
	if not url or not key:
		raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY in environment or .env")

	supabase = create_client(url, key)
	bucket = "files"

	with open(local_path, "rb") as f:
		data = f.read()
	# upload expects a file-like or bytes depending on client; passing bytes
	resp = supabase.storage.from_(bucket).upload(remote_path, data)
	print("Upload response:", resp)


def main():
	parser = argparse.ArgumentParser(description="Upload a file to Supabase storage bucket 'files'.")
	parser.add_argument("local_path", help="Local file path to upload")
	parser.add_argument("remote_path", nargs="?", help="Remote path in bucket (defaults to basename)")
	args = parser.parse_args()

	local = args.local_path
	remote = args.remote_path or os.path.basename(local)
	upload_file(local, remote)


if __name__ == "__main__":
	main()
