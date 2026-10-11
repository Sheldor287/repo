from openpyxl.styles import PatternFill
import pytesseract, cv2

# Path information
sc2_replay_folders = {
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\818120349\1-S2-1-12222818\Replays\Multiplayer": "Sheldor",  
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\872877221\1-S2-1-13167085\Replays\Multiplayer": "Skippy", 
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\882087899\1-S2-1-13284046\Replays\Multiplayer": "LarvaDaVinci",
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\883728609\1-S2-1-13315505\Replays\Multiplayer": "WrkinOnMyGme",
    r"C:\Users\Drew\Documents\StarCraft II\Accounts\959938012\1-S2-1-13558705\Replays\Multiplayer": "LtGmeIsHard",
}
my_names = set(sc2_replay_folders.values())
xlsx_path =  r"C:\Users\Drew\Documents\MyFiles\my-repo\data\sc2_games_log.xlsx"
lock_file = xlsx_path + ".lock"

# Colors
win_fill = PatternFill(start_color="65FC4E", end_color="65FC4E", fill_type="solid") 
loss_fill = PatternFill(start_color="FC514E", end_color="FC514E", fill_type="solid")  
tie_fill = PatternFill(start_color="4FCDFF", end_color="4FCDFF", fill_type="solid") 

# Parsing Constants
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
template = cv2.imread(r"C:\Users\Drew\Pictures\Screenshots\ANCHOR.png", 0)
anchor_roi = (440, 725, 225, 25)
rois = {
    'my_mmr': (670, 725, 110, 25),
    'my_change': (590, 755, 40, 20),
    'opp_mmr': (1435, 725, 110, 25),
}
detect_region = {"top": 291, "left": 182, "width": 1115, "height": 49}