import threading, time
from parse import monitor_for_replays_threaded

def sustain():
    while True:
        time.sleep(30)

def main():
    try:
        monitor_thread = threading.Thread(target=monitor_for_replays_threaded, daemon=True)
        monitor_thread.start()

        edit_thread = threading.Thread(target=sustain, daemon=True)
        edit_thread.start()

    except Exception as e:
        print(f"Error starting replay monitor: {e}. Restarting in 10 seconds.")
        time.sleep(10)
        main()

    while True:
        time.sleep(15)

if __name__ == "__main__":
    main()
