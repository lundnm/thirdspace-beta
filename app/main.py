import asyncio
import sys
from pathlib import Path

# Directory containing the pipeline scripts
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

async def run_script(script_name):
    print(f"\n{'='*40}")
    print(f"🚀 STARTING: {script_name}")
    print(f"{'='*40}")

    # sys.executable ensures it uses the same Python environment/venv
    # that you are currently running this master script in.
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(SCRIPTS_DIR / script_name),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(SCRIPTS_DIR)
    )

    # Wait for the script to finish and grab its output
    stdout, stderr = await process.communicate()

    # Check if the script ran successfully (return code 0 means success)
    if process.returncode == 0:
        if stdout:
            print(stdout.decode().strip())
        print(f"✅ FINISHED: {script_name}")
    else:
        # If the script crashed, print the error and raise an exception to stop the pipeline
        if stdout:
            print(stdout.decode().strip())
        if stderr:
            print(f"❌ ERROR in {script_name}:\n{stderr.decode().strip()}")

        raise RuntimeError(f"Pipeline halted because {script_name} failed.")

async def main():
    # 1. List your scripts here in the EXACT order they need to run.
    # (Update these names to match your actual files)
    scripts_in_order = [
        "DailyStreamingScraperV2.py",
        "stream_cleaningV2.py",
        "user_cleaning.py",
        "matching.py"
    ]

    print("Starting automated pipeline...")

    # 2. Loop through and run them one by one
    for script in scripts_in_order:
        try:
            await run_script(script)
        except RuntimeError as e:
            print(f"\n🛑 {e}")
            break # Stops the loop so downstream scripts don't run

    print("\n🎉 Pipeline execution complete!")

if __name__ == "__main__":
    asyncio.run(main())
