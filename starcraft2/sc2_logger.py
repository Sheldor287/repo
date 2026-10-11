import os, time, threading, sc2reader, warnings, pytesseract
import tempfile, shutil, psutil, gc, re, mss, cv2
import pandas as pd
import numpy as np
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from openpyxl import load_workbook
from openpyxl.styles import Alignment, PatternFill
from filelock import FileLock
from contextlib import contextmanager

@contextmanager
def timer(label):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"[TIME] {label}: {elapsed:.3f}s")


# Dictionary of replay folders mapped to SC2 accounts (Player names are mapped to folders)
SC2_REPLAY_FOLDERS = {
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\818120349\1-S2-1-12222818\Replays\Multiplayer": "Sheldor",  
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\872877221\1-S2-1-13167085\Replays\Multiplayer": "Skippy", 
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\882087899\1-S2-1-13284046\Replays\Multiplayer": "LarvaDaVinci",
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\883728609\1-S2-1-13315505\Replays\Multiplayer": "WrkinOnMyGme",
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\959938012\1-S2-1-13558705\Replays\Multiplayer": "LtGmeIsHard",
}
MY_PLAYER_NAMES = set(SC2_REPLAY_FOLDERS.values())
documents_folder = os.path.join(os.path.expanduser("~"), "Documents")
EXCEL_FILE = r"C:\Users\Drew\Documents\MyFiles\my-repo\data\sc2_games_log.xlsx"
LOCK_FILE = EXCEL_FILE + ".lock"

# Colors
WIN_FILL = PatternFill(start_color="65FC4E", end_color="65FC4E", fill_type="solid")  # Light Green, 60% Lighter
LOSS_FILL = PatternFill(start_color="FC514E", end_color="FC514E", fill_type="solid")  # Light Red, 60% Lighter
TIE_FILL = PatternFill(start_color="4FCDFF", end_color="4FCDFF", fill_type="solid")  # Light Blue, 60% Lighter

# Image Processing
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
template = cv2.imread(r"C:\Users\Drew\Pictures\Screenshots\ANCHOR.png", 0)
th, tw = template.shape
anchor_roi = (440, 725, 225, 25)
rois = {
    'my_mmr': (670, 725, 110, 25),
    'my_change': (590, 755, 40, 20),
    'opp_mmr': (1435, 725, 110, 25),
}
detect_region = {"top": 291, "left": 182, "width": 1115, "height": 49}

def is_end_screen(frame, threshold=0.8):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    max_val = np.max(res)
    print(f"Match score: {max_val:.3f}")
    return np.max(res) > threshold

def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return thresh

def ocr_number(img):
    processed = preprocess(img)
    config = '--psm 7 -c tessedit_char_whitelist=0123456789+-'
    text = pytesseract.image_to_string(processed, config=config)
    nums = re.findall(r'[+-]?\d+', text)
    return int(nums[0]) if nums else None

def crop(img, roi):
    x, y, w, h = roi
    return img[y:y+h, x:x+w]

def extract_mmr_values(full_img, rois):
    return {
        "my_mmr": ocr_number(crop(full_img, rois["my_mmr"])),
        "opp_mmr": ocr_number(crop(full_img, rois["opp_mmr"])),
        "mmr_change": ocr_number(crop(full_img, rois["my_change"]))
    }

def draw_rois(frame, rois, anchor_roi=anchor_roi):
    debug = frame.copy()

    if anchor_roi:
        x, y, w, h = anchor_roi
        cv2.rectangle(debug, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(debug, "ANCHOR", (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    for name, (x, y, w, h) in rois.items():
        cv2.rectangle(debug, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(debug, name, (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)


    cv2.waitKey(1)

def is_loading_screen(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    mean = np.mean(gray)
    std = np.std(gray)

    print(f"Loading screen: (mean, std) = ({mean:.1f}, {std:.1f})")

    # Tuned for your screenshots
    return (mean < 40) and (std < 40)

def is_anchor_detected(frame, threshold=0.7):

    x, y, w, h = anchor_roi
    crop = frame[y:y+h, x:x+w]

    # Example: use template matching with a stored anchor template
    # You can save your anchor template separately
    anchor_template = template

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(crop_gray, anchor_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    return max_val >= threshold

def wait_for_file_complete(path, stable_time=1):
    print('wait for complete')
    last_size = -1
    stable_count = 0
    while stable_count < stable_time:
        try:
            size = os.path.getsize(path)
        except OSError:
            size = -1
            print('error')
        if size == last_size:
            stable_count += 1
        else:
            stable_count = 0
        last_size = size
        time.sleep(0.1)

def attach_mmr_to_game_data(game_data, full_img, rois):
    mmr_values = extract_mmr_values(full_img, rois)
    if mmr_values["my_mmr"] is not None:
        game_data["My MMR"] = mmr_values["my_mmr"]
    if mmr_values["opp_mmr"] is not None:
        game_data["Opp MMR"] = mmr_values["opp_mmr"]
    if mmr_values["mmr_change"] is not None:
        game_data["MMR Change"] = mmr_values["mmr_change"]
    return game_data

def get_sheet_name(player_race):
    race_sheets = {"Zerg": "Zerg", "Terran": "Terran", "Protoss": "Protoss"}
    return race_sheets.get(player_race, "Unknown")


def parse_replay(replay_path):
    try:
        replay = sc2reader.load_replay(replay_path)
    
    except Exception as e:
        print(f"Error loading replay: {e}")
        return None

    # Check if in game
    player_names = {player.name for player in replay.players}
    if not MY_PLAYER_NAMES & player_names:  
        print("Skipping replay -- Observer.")
        return None
    # Skip if an AI player is present
    if any("A.I. 1" in name for name in player_names):
        print("Skipping replay -- Contains AI player.")
        return None
    if len(replay.players) != 2:
        print(f"[Info] Skipping replay with {len(replay.players)} players: {replay_path}")
        return None
    folder_path = os.path.dirname(replay_path)
    player_name = SC2_REPLAY_FOLDERS.get(folder_path)
    if not player_name:
        print(f"[Warning] Couldn't identify player for the replay in folder: {folder_path}")
        return None

    my_player = None
    opponent = None
    for player in replay.players:
        if player.name == player_name: 
            my_player = player
        else:
            opponent = player
    if not my_player or not opponent:
        print(f"[Warning] Couldn't identify both players in the replay: {replay_path}")
        return None
    # Get game data
    game_data = {
        "Date": replay.start_time.strftime("%Y-%m-%d %H:%M"),
        "Map": replay.map_name,
        "Duration (min)": round(replay.game_length.seconds / 60, 2),
        "Account": my_player.name,
        "My Race": my_player.play_race,
        "My MMR": "",  # Leave blank for manual entry
        "My Build": "",  # Leave blank for manual entry
        "Plan": "",  # Leave blank for manual entry
        "Opp Name": opponent.name,
        "Opp Race": opponent.play_race,
        "Opp-Build": "",  # Leave blank for manual entry
        "Opp MMR": "",  # Leave blank for manual entry
        "Comments": '',
        "Winner": replay.winner.players[0].name if replay.winner else "Unknown",
        "Source Folder": replay_path,
    }
    return game_data

####################################################
################ Write Excel Data ##################
####################################################

def load_existing_sheets():
    ''' Get the .xlsx file w/ the sheet for race played '''
    try:
        with pd.ExcelFile(EXCEL_FILE, engine="openpyxl") as xls:
            sheets = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
    except FileNotFoundError:
        sheets = {"Zerg": pd.DataFrame(), "Terran": pd.DataFrame(), "Protoss": pd.DataFrame()}
    return sheets


def prepare_new_data(game_data):
    """Prepare the new game data and drop unnecessary columns."""
    new_df = pd.DataFrame([game_data])
    new_df.drop(columns=["My Race"], inplace=True, errors="ignore")
    new_df = new_df.dropna(axis=1, how='all')  # Drop completely empty columns
    return new_df


def update_sheet_data(sheets, sheet_name, new_df):
    
    # Ensure the sheet has the correct columns
    warnings.simplefilter(action='ignore', category=FutureWarning)
    if sheet_name not in sheets or sheets[sheet_name].empty:
        sheets[sheet_name] = pd.DataFrame(columns=new_df.columns)
    
    # Append the new data (only if it's non-empty)
    sheets[sheet_name] = pd.concat([sheets[sheet_name], new_df], ignore_index=True, sort=False)


def save_to_temp_file(sheets):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", mode='w+b') as temp_file:
        temp_path = temp_file.name  

    with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
        for sheet, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    shutil.move(temp_path, EXCEL_FILE)  # This handles all files --> edit while open


def apply_formatting(wb, sheet_name, game_data):

    for sheet in wb.worksheets:
        header_row = [cell.value for cell in sheet[1]]

        # Auto-size columns
        for col in sheet.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            sheet.column_dimensions[col_letter].width = max_length + 2 

        # Center-align
        for row_idx, row in enumerate(sheet.iter_rows(), start=1):
            if row_idx > 1:
                for cell in row:
                    cell.alignment = Alignment(horizontal='center', vertical='center')

        # Apply Win-Loss Color
        if "Winner" in header_row:
            result_col_idx = header_row.index("Winner") + 1  
        else:
            result_col_idx = None

        for row_idx in range(2, sheet.max_row + 1):  
            result_cell = sheet.cell(row=row_idx, column=result_col_idx)
            result = str(result_cell.value).strip() if result_cell.value else "Unknown"

            if result in SC2_REPLAY_FOLDERS.values():
                row_fill = WIN_FILL  
            elif result == "Unknown" or not result:
                row_fill = TIE_FILL  
            else:
                row_fill = LOSS_FILL  

            for cell in sheet[row_idx]:  
                cell.fill = row_fill


def rename_and_open_file(game_data):
    rename_replay_file(game_data["Source Folder"], game_data)
    time.sleep(0.5)
    os.startfile(EXCEL_FILE) 
    


#################################################################
################### Main Excel Writing Logic ####################
#################################################################

def update_excel(game_data):
    lock = FileLock(LOCK_FILE)

    try:
        with lock:
            sheets = load_existing_sheets()
            sheet_name = get_sheet_name(game_data["My Race"])
            new_df = prepare_new_data(game_data)

            update_sheet_data(sheets, sheet_name, new_df)

            save_to_temp_file(sheets)

            try:
                wb = load_workbook(EXCEL_FILE)
                apply_formatting(wb, sheet_name, game_data)
                wb.active = wb.sheetnames.index(sheet_name)
                wb.save(EXCEL_FILE)
                wb.close()
            except Exception as e:
                print(f"Warning: Could not format Excel file. Error: {e}")

            gc.collect()

        rename_and_open_file(game_data)

    except Exception as e:
        print(f"Error updating Excel: {e}. Skipping this update and restarting.")

#################################################################
################## SCII Document Scanner Logic ##################
#################################################################
    
class ReplayHandler(FileSystemEventHandler):
    def __init__(self, timeout=60*60):
        """timeout: max seconds to wait for end screen before skipping OCR"""
        super().__init__()
        self.timeout = timeout  # seconds

    def process_replay(self, replay_path):
        clock = 0
        print(f"New replay detected: {replay_path}")
        with timer('waiting for file complete'):
            wait_for_file_complete(replay_path)
        with timer('parse replay'):
            game_data = parse_replay(replay_path)
        if not game_data:
            return

        while is_file_in_use(replay_path):
            clock += 1
            print(f"File {replay_path} still in use...")
            time.sleep(0.5)
        
        # -----------------------
        # State machine
        # -----------------------
        state = "WAITING_FOR_LOADING"
        captured = False
        DEBUG_ROIS = True
        prev_frame = None

        anchor_hits = 0
        stable_frames = 0

        start_time = time.time()

        with mss.MSS() as sct:

            while not captured:

                if time.time() - start_time > self.timeout:
                    print("Timeout reached.")
                    update_excel(game_data)
                    rename_replay_file(replay_path, game_data)
                    break

                frame = np.array(sct.grab({
                    "top": 0,
                    "left": 0,
                    "width": 1920,
                    "height": 1080
                }))

                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Loading Screen

                if state == "WAITING_FOR_LOADING":
                    if is_loading_screen(frame):
                        print("Loading detected")
                        state = "WAITING_FOR_MENU"
                        anchor_hits = 0

                # Menu
                elif state == "WAITING_FOR_MENU":
                    if is_anchor_detected(frame):
                        anchor_hits += 1
                        time.sleep(0.8)

                    else:
                        anchor_hits = 0
                    if anchor_hits >= 3:
                        print("Anchor stabilized")
                        state = "WAIT_FOR_STABLE_FRAME"
                        stable_frames = 0


                # Static Image
                elif state == "WAIT_FOR_STABLE_FRAME":

                    if prev_frame is None:
                        prev_frame = frame.copy()
                        continue


                    diff = cv2.absdiff(prev_frame, frame)
                    motion = np.mean(diff)

                    if motion < 2:
                        stable_frames += 1

                    else:
                        stable_frames = 0
                    if stable_frames >= 3:

                        print("Frame stable → OCR")

                        if DEBUG_ROIS:
                            draw_rois(frame, rois)

                        game_data = attach_mmr_to_game_data(game_data,frame,rois)
                        update_excel(game_data)
                        captured = True
                        break

                prev_frame = frame.copy()
                time.sleep(0.5)


    def on_created(self, event):
        clock = 0
        replay_path = event.src_path
        if event.is_directory or not event.src_path.endswith(".SC2Replay"):
            return
        threading.Thread(target=self.process_replay, args=(event.src_path,), daemon=True).start()


# Monitor for replays
def monitor_for_replays():
    observers = []
    for folder, player in SC2_REPLAY_FOLDERS.items():
        observer = Observer()
        event_handler = ReplayHandler()
        observer.schedule(event_handler, folder, recursive=False)
        observer.start()
        observers.append(observer)
        print(f"Monitoring {folder} for new SC2 replays...")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        for observer in observers:
            observer.stop()
        for observer in observers:
            observer.join()
        print("Stopped monitoring.")


# Periodic edit function 
def edit_excel():
    while True:
        time.sleep(30)  


def rename_replay_file(replay_path, game_data):
    """Renames the replay file based on game details."""

    folder = os.path.dirname(replay_path)

    # Extract relevant details
    my_race = game_data["My Race"][0]
    opp_race = game_data["Opp Race"][0]
    opp_name = game_data["Opp Name"]
    map_name = game_data["Map"]

    result = ("Win"if game_data["Winner"] == game_data["Account"]else "Loss")

    matchup = f"({my_race}v{opp_race})"

    base_filename = (f"{matchup} -- {opp_name}, {map_name}, {result}")

    # Remove invalid filename characters
    base_filename = re.sub(r'[<>:"/\\|?*]', '', base_filename)

    # Wait until file is free
    while is_file_in_use(replay_path):
        print("Waiting for file to be released...")
        time.sleep(0.5)

    # Count existing matches
    existing_replays = [f for f in os.listdir(folder)if base_filename in f]
    match_count = len(existing_replays) + 1
    new_filename = (f"{base_filename} ({match_count}).SC2Replay")

    new_path = os.path.join(folder, new_filename)

    try:
        os.rename(replay_path, new_path)
        print(f"Replay renamed to: {new_filename}")

    except Exception as e:
        print(f"Error renaming replay: {e}")


def is_file_in_use(file_path):
    """Check if the file is being used by another process."""
    try:
        with open(file_path, 'a'):
            return False
    except IOError:
        return True


def monitor_for_replays_threaded():
    observers = []
    for folder, player in SC2_REPLAY_FOLDERS.items():
        observer = Observer()
        event_handler = ReplayHandler(timeout=120)
        observer.schedule(event_handler, folder, recursive=False)
        observer.start()
        observers.append(observer)

    try:
        while True:
            time.sleep(5)  # Keep main thread alive
    except KeyboardInterrupt:
        for observer in observers:
            observer.stop()
        for observer in observers:
            observer.join()
        print("Stopped monitoring.")

# Start monitoring and Excel threads safely
def main_loop():
    try:
        # Start the replay monitoring thread
        monitor_thread = threading.Thread(target=monitor_for_replays_threaded, daemon=True)
        monitor_thread.start()

        # Start the Excel editing thread (already periodic)
        edit_thread = threading.Thread(target=edit_excel, daemon=True)
        edit_thread.start()

        print("Pipeline running. Waiting for replays...")

        # Keep main thread alive
        while True:
            time.sleep(15)

    except Exception as e:
        print(f"Error detected: {e}. Restarting in 10 seconds...")
        time.sleep(10)
        main_loop()  # Restart loop if failure occurs

# Start the full pipeline
main_loop()



