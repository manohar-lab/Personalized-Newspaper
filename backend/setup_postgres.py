import os
import sys
import zipfile
import urllib.request
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PG_DIR = os.path.join(BASE_DIR, "pgsql")
DATA_DIR = os.path.join(PG_DIR, "data")
BIN_DIR = os.path.join(PG_DIR, "pgsql", "bin") if os.path.exists(os.path.join(PG_DIR, "pgsql", "bin")) else os.path.join(PG_DIR, "bin")
ZIP_FILE = os.path.join(BASE_DIR, "postgresql-binaries.zip")
URL = "https://get.enterprisedb.com/postgresql/postgresql-15.3-1-windows-x64-binaries.zip"


def download_progress(count, block_size, total_size):
    percent = int(count * block_size * 100 / total_size)
    mb = (count * block_size) / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    sys.stdout.write(f"\rDownloading PostgreSQL binaries: {percent}% ({mb:.1f}/{total_mb:.1f} MB)")
    sys.stdout.flush()


def setup_postgresql():
    bin_dir = BIN_DIR
    if not os.path.exists(os.path.join(bin_dir, "postgres.exe")):
        # Check if pgsql subdirectory exists after extraction
        if os.path.exists(os.path.join(PG_DIR, "pgsql", "bin", "postgres.exe")):
            bin_dir = os.path.join(PG_DIR, "pgsql", "bin")

    if not os.path.exists(os.path.join(bin_dir, "postgres.exe")):
        if not os.path.exists(ZIP_FILE):
            print("Downloading PostgreSQL portable binaries...")
            req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(ZIP_FILE, 'wb') as out_file:
                total_length = response.headers.get('content-length')
                if total_length is None:
                    out_file.write(response.read())
                else:
                    dl = 0
                    total_length = int(total_length)
                    chunk_size = 1024 * 1024
                    while True:
                        buffer = response.read(chunk_size)
                        if not buffer:
                            break
                        dl += len(buffer)
                        out_file.write(buffer)
                        percent = int(dl * 100 / total_length)
                        sys.stdout.write(f"\rDownloading PostgreSQL binaries: {percent}% ({dl / (1024*1024):.1f}/{total_length / (1024*1024):.1f} MB)")
                        sys.stdout.flush()
            print("\nDownload complete.")

        print("Extracting PostgreSQL binaries...")
        with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
            zip_ref.extractall(PG_DIR)
        print("Extraction complete.")

    # Re-evaluate bin_dir
    if os.path.exists(os.path.join(PG_DIR, "pgsql", "bin", "postgres.exe")):
        bin_dir = os.path.join(PG_DIR, "pgsql", "bin")
    else:
        bin_dir = os.path.join(PG_DIR, "bin")

    initdb_exe = os.path.join(bin_dir, "initdb.exe")
    pg_ctl_exe = os.path.join(bin_dir, "pg_ctl.exe")
    createdb_exe = os.path.join(bin_dir, "createdb.exe")

    # Initialize data cluster if not already present
    if not os.path.exists(DATA_DIR) or not os.listdir(DATA_DIR):
        print("Initializing database cluster with initdb...")
        pw_file = os.path.join(BASE_DIR, "pwfile.txt")
        with open(pw_file, "w") as f:
            f.write("postgres")

        cmd = [
            initdb_exe,
            "-D", DATA_DIR,
            "-U", "postgres",
            "-A", "scram-sha-256",
            f"--pwfile={pw_file}",
            "-E", "UTF8"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(pw_file):
            os.remove(pw_file)
        if res.returncode != 0:
            print("initdb failed:", res.stderr)
            return False
        print("Database cluster initialized.")

    # Check status or start server
    print("Starting PostgreSQL server...")
    log_file = os.path.join(PG_DIR, "pgsql.log")
    start_cmd = [pg_ctl_exe, "-D", DATA_DIR, "-l", log_file, "start"]
    res = subprocess.run(start_cmd, capture_output=True, text=True)
    print("pg_ctl output:", res.stdout, res.stderr)

    time.sleep(2)

    # Create database if not existing
    print("Creating database 'personalized_newspaper'...")
    createdb_cmd = [createdb_exe, "-U", "postgres", "-h", "localhost", "-p", "5432", "personalized_newspaper"]
    env = os.environ.copy()
    env["PGPASSWORD"] = "postgres"
    res = subprocess.run(createdb_cmd, capture_output=True, text=True, env=env)
    print("createdb output:", res.stdout, res.stderr)

    print("PostgreSQL setup & start successfully completed!")
    return True


if __name__ == "__main__":
    setup_postgresql()
