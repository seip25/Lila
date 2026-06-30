import os
import sys
import subprocess

def main():
    """
    Start the Lila local development server by executing main.py.
    """
    if not os.path.exists("main.py"):
        print(" Error: main.py not found in the current directory.")
        print("   Make sure you are in the root directory of your Lila project.")
        sys.exit(1)
        
    print("🚀 Starting Lila development server...")
    try:
        # Run python main.py
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n Lila server stopped.")
    except Exception as e:
        print(f" Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
