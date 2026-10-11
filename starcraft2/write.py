import os, time, warnings, tempfile, shutil, re, gc
import pandas as pd
from filelock import FileLock
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Alignment
from constants import sc2_replay_folders, xlsx_path, lock_file, win_fill, loss_fill, tie_fill
from logger import logger
from logging.handlers import RotatingFileHandler

def update_excel(game_data):
    lock = FileLock(lock_file)

    with lock:
        if os.path.exists(xlsx_path):
            wb = load_workbook(xlsx_path)
        else:
            wb = Workbook()
        sheet_name = get_sheet_name(game_data["My Race"])
        if sheet_name not in wb.sheetnames:
            ws = wb.create_sheet(sheet_name)
            ws.append(list(game_data.keys()))
        else:
            ws = wb[sheet_name]
        headers = [cell.value for cell in ws[1]]
        row = [game_data.get(header, "") for header in headers]
        ws.append(row)
        for sheet in wb.sheetnames:
            apply_formatting(wb[sheet])
        wb.save(xlsx_path)
        wb.close()

def update_excel_OLD(game_data):
    lock = FileLock(lock_file)

    try:
        with lock:
            sheets = load_existing_sheets()
            sheet_name = get_sheet_name(game_data["My Race"])
            new_df = prepare_new_data(game_data)

            update_sheet_data(sheets, sheet_name, new_df)

            save_to_temp_file(sheets)

            try:
                wb = load_workbook(xlsx_path)
                for sheet in wb.sheetnames:
                    apply_formatting(wb[sheet])
                wb.active = wb.sheetnames.index(sheet_name)
                wb.save(xlsx_path)
                wb.close()
            except Exception as e:
                print(f"Warning: Could not format Excel file. Error: {e}")

            gc.collect()

        rename_and_open_file(game_data)

    except Exception as e:
        print(f"Error updating Excel: {e}. Skipping this update and restarting.")

def load_existing_sheets():
    ''' Get the .xlsx file w/ the sheet for race played '''
    try:
        with pd.ExcelFile(xlsx_path, engine="openpyxl") as xls:
            sheets = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
    except FileNotFoundError:
        sheets = {"Zerg": pd.DataFrame(), "Terran": pd.DataFrame(), "Protoss": pd.DataFrame()}
    return sheets

def get_sheet_name(player_race):
    race_sheets = {"Zerg": "Zerg", "Terran": "Terran", "Protoss": "Protoss"}
    return race_sheets.get(player_race, "Unknown")

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

    shutil.move(temp_path, xlsx_path)  # This handles all files --> edit while open

def apply_formatting(sheet):

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
                cell.alignment = Alignment(
                    horizontal='center',
                    vertical='center'
                )

    # Winner column
    if "Winner" in header_row:
        result_col_idx = header_row.index("Winner") + 1
    else:
        return

    # Row coloring
    for row_idx in range(2, sheet.max_row + 1):

        result_cell = sheet.cell(row=row_idx, column=result_col_idx)

        result = (
            str(result_cell.value).strip()
            if result_cell.value
            else "Unknown"
        )

        if result in sc2_replay_folders.values():
            row_fill = win_fill

        elif result == "Unknown":
            row_fill = tie_fill

        else:
            row_fill = loss_fill

        for cell in sheet[row_idx]:
            cell.fill = row_fill

def rename_replay_file(replay_path, game_data):
    """Rename a 1v1 replay without determining its result."""
    my_race = game_data["My Race"][0]
    opp_race = game_data["Opp Race"][0]
    opp_name = game_data["Opp Name"]
    map_name = game_data["Map"]
    matchup = f"({my_race}v{opp_race})"
    base_filename = (f"{matchup} -- {opp_name}, {map_name}")
    return rename_replay(replay_path,base_filename,)

def rename_replay_file_team(replay_path, replay):
    """Rename a team/multiplayer replay without determining Win/Loss."""
    team_list = get_team(replay)
    if not team_list:
        logger.warning("Could not determine team for replay: %s", replay_path)
        return None
    team_string = ", ".join(team_list)
    base_filename = (f"{team_string}, {replay.map_name}, Teams")
    return rename_replay(replay_path,base_filename,)


def rename_replay(replay_path, base_filename):
    """
    Rename a replay using a unique filename.
    Returns the new path on success, otherwise None.
    """
    folder = os.path.dirname(replay_path)
    base_filename = re.sub(r'[<>:"/\\|?*]','',base_filename,)

    # Wait until SC2 releases the file.
    while is_file_in_use(replay_path):
        logger.debug(
            "Waiting for replay file to be released: %s", replay_path,
        )
        time.sleep(0.25)

    existing_replays = [
        f for f in os.listdir(folder) if f.startswith(base_filename) and f.lower().endswith(".sc2replay")
    ]
    match_count = len(existing_replays) + 1
    new_filename = (f"{base_filename} ({match_count}).SC2Replay")
    new_path = os.path.join(folder,new_filename,)

    try:
        os.rename(replay_path, new_path)

        logger.info(
            "Replay renamed: %s -> %s", os.path.basename(replay_path), new_filename,
        )

        return new_path

    except OSError:
        logger.exception(
            "Failed to rename replay: %s", replay_path,
        )
        return None

def rename_and_open_file(game_data):
    rename_replay_file(game_data["Source Folder"], game_data)
    time.sleep(0.5)


def is_file_in_use(file_path):
    """Check if the file is being used by another process."""
    try:
        os.rename(file_path, file_path)
        return False
    except OSError:
        return True
    
def get_team(replay, my_names=sc2_replay_folders.values()):
    if len(replay.players) != 2:
        name_list = [player.name for player in replay.players]
        midp = len(name_list) // 2
        first_half = name_list[:midp]
        if any(player in first_half for player in my_names):
            return first_half
        else: 
            return name_list[midp:]
    
def rename_replay_file_team(replay_path, replay, attempts=0, success=False):
    for attempts in range(5):
        try: 
            folder = os.path.dirname(replay_path)
            team_list = get_team(replay)
            team_string = ", ".join(team_list)
            map_name = replay.map_name
            if not hasattr(replay, "results"):
                result = "Teams"
            else:
                result = "Win" if replay.winner.players[0].name in team_list else "Loss"
            base_filename = f"{team_string}, {map_name}, {result}"
            existing_replays = [f for f in os.listdir(folder) if base_filename in f]
            match_count = len(existing_replays) + 1
            new_filename = f"{base_filename} ({match_count}).SC2Replay"
            os.rename(replay_path, os.path.join(folder, new_filename))
            print(f"Replay renamed to: {new_filename}")
            break
        
        except:
            print(f"Attempt {attempts+1}/5")
            print(f"Replay path: {replay_path}")
            print(f"Replay name: {new_filename}")
            time.sleep(10)



