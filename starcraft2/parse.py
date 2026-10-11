import os, time, threading, numpy as np
import sc2reader, mss, cv2
from contextlib import contextmanager
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from constants import sc2_replay_folders, my_names, rois
from write import  update_excel, rename_replay_file, rename_replay_file_team #, is_file_in_use, rename_replay_file
from image import ocr_number,crop,is_loading_screen,is_anchor_detected #,draw_rois
from logger import logger


@contextmanager
def timer(label):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.debug("%s: %.3fs", label, elapsed)


class ReplayHandler(FileSystemEventHandler):

    def __init__(self,timeout=120,poll_interval=0.1,mmr_stable_reads=3,):
        super().__init__()

        self.timeout = timeout
        self.poll_interval = poll_interval
        self.mmr_stable_reads = mmr_stable_reads
        self.processing = set()
        self.processing_lock = threading.Lock()
        self.screen_lock = threading.Lock()

    def process_replay(self, replay_path):

        logger.info("New replay detected: %s", replay_path)
        with timer("waiting for file complete"):
            wait_for_file_complete(replay_path)

        with timer("parse replay"):
            replay = load_replay(replay_path)

        if replay is None:
            return

        # Replay classification
        player_names = {player.name for player in replay.players}

        if not my_names & player_names:
            logger.info("Replay is not one of ours: %s", replay_path,)
            return

        if any("A.I. 1" in name for name in player_names):
            logger.info("AI replay skipped: %s", replay_path,)
            return
        
        # Team replays
        if len(replay.players) > 2:
            logger.info(
                "Team replay detected (%d players): %s", len(replay.players), replay_path,
            )
            rename_replay_file_team(replay_path,replay,)
            return

        # 1v1 replay
        game_data = build_game_data(replay_path,replay,)
        if game_data is None:
            return

        # Rename now, before interacting with the UI.
        new_path = rename_replay_file(replay_path,game_data,)

        if new_path is None:
            logger.warning("Could not rename replay; continuing: %s",replay_path,)

        # Screen capture
        with self.screen_lock:
            mmr_values = self.capture_mmr(replay_path)
        attach_mmr_to_game_data(game_data,mmr_values,)
        update_excel(game_data)
        logger.info("Replay processed successfully: %s",replay_path,)

    # Capture Logic
    def capture_mmr(self, replay_path):

        state = "WAITING_FOR_LOADING"
        start_time = time.monotonic()
        anchor_hits = 0
        previous_mmr = None
        stable_mmr_reads = 0

        with mss.MSS() as sct:

            while True:
                elapsed = time.monotonic() - start_time
                if elapsed > self.timeout:
                    logger.warning(
                        "Score screen timeout after %.1fs: %s",elapsed,replay_path,
                    )
                    return {}

                frame = capture_screen(sct)

                # Loading screen
                if state == "WAITING_FOR_LOADING":
                    if is_loading_screen(frame):
                        state = "WAITING_FOR_MENU"
                        anchor_hits = 0

                # Score screen
                elif state == "WAITING_FOR_MENU":
                    if is_anchor_detected(frame):
                        anchor_hits += 1
                    else:
                        anchor_hits = 0
                    if anchor_hits >= self.mmr_stable_reads:
                        state = "READING_MMR"
                        previous_mmr = None
                        stable_mmr_reads = 0

                # Capture MMR
                elif state == "READING_MMR":
                    mmr_values = extract_mmr_values(frame, rois)
                    my_mmr = mmr_values.get("my_mmr")

                    if my_mmr is None:
                        stable_mmr_reads = 0

                    elif my_mmr == previous_mmr:
                        stable_mmr_reads += 1

                    else:
                        logger.debug("MMR changed: %s -> %s",previous_mmr,my_mmr,)

                        previous_mmr = my_mmr
                        stable_mmr_reads = 1

                    if stable_mmr_reads >= self.mmr_stable_reads:
                        logger.info("Stable MMR detected: %s",my_mmr,)
                        return mmr_values

                time.sleep(self.poll_interval)



    def process_replay_wrapper(self, replay_path):

        try:
            self.process_replay(replay_path)

        except Exception:
            logger.exception(
                "Unhandled exception processing replay: %s",replay_path,
                )

        finally:
            with self.processing_lock:
                self.processing.discard(replay_path)

    def on_created(self, event):

        if event.is_directory:
            return

        replay_path = event.src_path

        if not replay_path.lower().endswith(".sc2replay"):
            return

        with self.processing_lock:

            if replay_path in self.processing:
                logger.debug(
                    "Replay already processing: %s",
                    replay_path,
                )
                return

            self.processing.add(replay_path)

        logger.debug(
            "Starting replay worker: %s",
            replay_path,
        )

        threading.Thread(
            target=self.process_replay_wrapper,
            args=(replay_path,),
            daemon=True,
        ).start()


# Helpers
def wait_for_file_complete(path,stable_time=1.0,poll_interval=0.1,):

    last_size = None
    stable_since = None

    while True:

        try:
            size = os.path.getsize(path)

        except OSError:
            size = None

        now = time.monotonic()

        if size is not None and size == last_size:

            if stable_since is None:
                stable_since = now

            elif now - stable_since >= stable_time:
                return

        else:
            stable_since = None
            last_size = size

        time.sleep(poll_interval)


def load_replay(replay_path):

    try:
        return sc2reader.load_replay(replay_path)

    except Exception:
        logger.exception(
            "Exception parsing replay: %s",
            replay_path,
        )
        return None


def build_game_data(replay_path, replay):

    player_names = {
        player.name
        for player in replay.players
    }

    # Not one of our games.
    if not my_names & player_names:
        return None

    # AI game.
    if any("A.I. 1" in name for name in player_names):
        logger.info(
            "AI replay skipped: %s",
            replay_path,
        )
        return None

    # Team/multiplayer games should be handled before this function
    # is called, so this should always be a 1v1 replay.
    if len(replay.players) != 2:
        logger.warning(
            "Unexpected player count (%d): %s",
            len(replay.players),
            replay_path,
        )
        return None

    folder_path = os.path.dirname(replay_path)

    player_name = sc2_replay_folders.get(folder_path)

    if not player_name:
        logger.warning(
            "Couldn't identify player for replay folder: %s",
            folder_path,
        )
        return None

    my_player = None
    opponent = None

    for player in replay.players:

        if player.name == player_name:
            my_player = player
        else:
            opponent = player

    if not my_player or not opponent:
        logger.warning(
            "Couldn't identify both players: %s",
            replay_path,
        )
        return None

    return {
        "Date": replay.start_time.strftime("%Y-%m-%d %H:%M"),
        "Map": replay.map_name,
        "Duration (min)": round(
            replay.game_length.seconds / 60,
            2,
        ),
        "Account": my_player.name,

        "My Race": my_player.play_race,
        "My MMR": "",
        "My Build": "",
        "Plan": "",

        "Opp Name": opponent.name,
        "Opp Race": opponent.play_race,
        "Opp-Build": "",
        "Opp MMR": "",

        "Comments": "",

        "Winner": (
            replay.winner.players[0].name
            if replay.winner
            else "Unknown"
        ),

        "Source Folder": replay_path,
    }

# Screen helper
def capture_screen(sct):
    frame = np.array(
        sct.grab({"top": 0,"left": 0,"width": 1920,"height": 1080,})
    )
    return cv2.cvtColor(frame,cv2.COLOR_BGRA2BGR,)

def extract_mmr_values(full_img, rois):
    return {
        "my_mmr": ocr_number(crop(full_img, rois["my_mmr"])),
        "opp_mmr": ocr_number(crop(full_img, rois["opp_mmr"])),
        "mmr_change": ocr_number(crop(full_img, rois["my_change"])),
    }

def attach_mmr_to_game_data(game_data, mmr_values):
    if mmr_values.get("my_mmr") is not None:
        game_data["My MMR"] = mmr_values["my_mmr"]
    if mmr_values.get("opp_mmr") is not None:
        game_data["Opp MMR"] = mmr_values["opp_mmr"]
    if mmr_values.get("mmr_change") is not None:
        game_data["MMR Change"] = mmr_values["mmr_change"]
    return game_data

def monitor_for_replays_threaded():
    observers = []
    event_handler = ReplayHandler(timeout=120)
    for folder in sc2_replay_folders:
        observer = Observer()
        observer.schedule(event_handler,folder,recursive=False,)
        observer.start()
        observers.append(observer)
        logger.info("Monitoring replay folder: %s",folder,)
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Stopping replay monitors...")
        for observer in observers:
            observer.stop()
        for observer in observers:
            observer.join()
        logger.info("Replay monitoring stopped.")