import os
import subprocess

def run():
    res = subprocess.run(
        [".\\venv\\Scripts\\python.exe", "manage.py", "test", "tests.test_scenarios", "--noinput"],
        capture_output=True,
        text=True
    )
    with open("test_output.txt", "w", encoding="utf-8") as f:
        f.write(res.stdout)
        f.write("\n--- STDERR ---\n")
        f.write(res.stderr)

if __name__ == "__main__":
    run()
