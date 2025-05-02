# --- START OF FILE caro_logic.py ---
# --- START OF FILE caro_logic.py (V3 Score-Driven - Learns Win/Loss - AutoSave V4) ---
import random
import time
import json
import os
import copy
from collections import defaultdict
import traceback
import math

# Định nghĩa người chơi và ô trống
PLAYER_X = 'X'
PLAYER_O = 'O'
EMPTY = '.'

# --- Hằng số điểm đánh giá (V3) ---
SCORE_WIN = math.inf
SCORE_BLOCK_WIN = 1000000
SCORE_CREATE_OPEN_4 = 500000
SCORE_BLOCK_OPEN_4 = 450000
SCORE_BLOCK_OPEN_3 = 100000
SCORE_CREATE_FORK_OPEN3 = 80000
SCORE_CREATE_HALF_OPEN_4 = 50000
SCORE_BLOCK_FORK = 40000
SCORE_BLOCK_HALF_OPEN_4 = 30000
SCORE_CREATE_OPEN_3 = 20000
SCORE_BLOCK_HALF_OPEN_3 = 5000
SCORE_CREATE_HALF_OPEN_3 = 2000
SCORE_CREATE_OPEN_2 = 200
SCORE_BLOCK_OPEN_2 = 100
SCORE_CREATE_HALF_OPEN_2 = 20
SCORE_BLOCK_HALF_OPEN_2 = 10
SCORE_POSITIONAL = 1

# --- Hàm factory mặc định ---
def default_win_entry():
    """Giá trị mặc định cho state -> winning_move (None ban đầu)."""
    return None
def default_losing_moves_entry():
    """Giá trị mặc định cho state -> set_of_losing_moves."""
    return set()

# --- Lớp Logic Caro ---
class CaroLogic:
    """
    Quản lý trạng thái bàn cờ, luật chơi Caro, kiểm tra thắng,
    tìm nước đi cho AI sử dụng logic V3, học từ các nước đi thắng và thua của AI.
    """
    def __init__(self, board_size=19, training_data_path="data.json", use_training_data=True, training_data_ref=None):
        """
        Khởi tạo logic game.

        Args:
            board_size (int): Kích thước bàn cờ (N x N).
            training_data_path (str): Đường dẫn file dữ liệu JSON (chứa cả wins và losses).
            use_training_data (bool): Có sử dụng dữ liệu đã học không.
            training_data_ref (dict | None): Tham chiếu đến dữ liệu dùng chung (từ trainer).
                                               Cấu trúc: {'wins': defaultdict, 'losses': defaultdict}
        """
        # ---- 1. Thiết lập cơ bản ---
        if not isinstance(board_size, int) or board_size < 5:
            print(f"Logic Warning: Kích thước bàn cờ không hợp lệ {board_size}. Đặt về 19.")
            self.board_size = 19
        else:
            self.board_size = board_size
        self.win_length = 5 # Số quân liên tiếp để thắng

        # ---- 2. Thiết lập đường dẫn và trạng thái sử dụng data ----
        self.training_data_path = training_data_path
        self.use_training_data_setting = use_training_data
        self.load_error = None
        self.directions = [(0, 1), (1, 0), (1, 1), (1, -1)] # Ngang, Dọc, Chéo chính, Chéo phụ

        # ---- 3. Khởi tạo/Tham chiếu dữ liệu ---
        # Đổi tên `training_data` thành `ai_winning_moves` để rõ nghĩa hơn
        self.ai_winning_moves = None # Dữ liệu state -> winning_move_by_AI
        self.losing_moves_data = None # Dữ liệu state -> set_of_losing_moves_by_AI

        if training_data_ref is not None and isinstance(training_data_ref, dict):
             # Dùng tham chiếu từ trainer (ít dùng trong game chính)
             # Giả định key trong ref là 'wins' và 'losses'
             self.ai_winning_moves = training_data_ref.get('wins', defaultdict(default_win_entry))
             self.losing_moves_data = training_data_ref.get('losses', defaultdict(default_losing_moves_entry))
             # print(f"Logic Info: Using shared data ref (Wins: {len(self.ai_winning_moves)}, Losses: {len(self.losing_moves_data)}).")
        elif self.use_training_data_setting:
            # Tải từ file nếu được yêu cầu
            self._load_combined_training_data()
        else:
             # Không dùng data, khởi tạo dict rỗng
             # print("Logic Info: Training data usage is disabled.")
             self.ai_winning_moves = defaultdict(default_win_entry)
             self.losing_moves_data = defaultdict(default_losing_moves_entry)

        # Đảm bảo các cấu trúc dữ liệu không bao giờ là None sau khi khởi tạo
        if self.ai_winning_moves is None:
             print("Logic CRITICAL ERROR: ai_winning_moves is None! Creating empty defaultdict.")
             self.ai_winning_moves = defaultdict(default_win_entry)
        if self.losing_moves_data is None:
             print("Logic CRITICAL ERROR: losing_moves_data is None! Creating empty defaultdict.")
             self.losing_moves_data = defaultdict(default_losing_moves_entry)

        print(f"CaroLogic V4 (AutoSave) Initialized: Board={self.board_size}x{self.board_size}, WinLen={self.win_length}, Path='{self.training_data_path}', UseData={self.use_training_data_setting}, Wins={len(self.ai_winning_moves)}, Losses={len(self.losing_moves_data)}, LoadErr='{self.load_error}'")

    # --- Các hàm tiện ích chuyển đổi định dạng key bàn cờ (LÀ INSTANCE METHODS) ---
    def board_tuple_to_string_key(self, board_tuple):
        """Chuyển đổi tuple bàn cờ thành chuỗi khóa."""
        if not board_tuple or not isinstance(board_tuple, tuple):
            # print(f"DEBUG board_tuple_to_string_key: Input không phải tuple hoặc rỗng: {type(board_tuple)}")
            return ""
        try:
            # Nối các phần tử trong mỗi hàng thành chuỗi, sau đó nối các chuỗi hàng lại
            return "".join("".join(map(str, row)) for row in board_tuple)
        except Exception as e:
            print(f"ERROR in board_tuple_to_string_key for {board_tuple}: {e}")
            return ""

    def string_key_to_board_tuple(self, string_key):
        """Chuyển đổi chuỗi khóa trở lại thành tuple bàn cờ."""
        board_size = self.board_size # Sử dụng board_size của instance
        if not isinstance(string_key, str) or not isinstance(board_size, int) or board_size <= 0:
            # print(f"DEBUG string_key_to_board_tuple: Invalid input type/value (key type={type(string_key)}, size={board_size})")
            return None
        expected_len = board_size * board_size
        if len(string_key) != expected_len:
            # print(f"DEBUG string_key_to_board_tuple: Invalid key length {len(string_key)} for size {board_size}.")
            return None
        try:
            rows = []
            # Chia chuỗi thành các đoạn tương ứng với từng hàng
            for i in range(0, expected_len, board_size):
                # Tạo tuple cho mỗi hàng
                row_tuple = tuple(string_key[i : i + board_size])
                rows.append(row_tuple)
            # Tạo tuple chứa các tuple hàng
            return tuple(rows)
        except Exception as e:
            # Ghi lại lỗi nếu quá trình chuyển đổi thất bại
            print(f"ERROR converting string key '{string_key}' to tuple (size={board_size}): {e}")
            return None
    # --- Kết thúc hàm tiện ích ---

    # --- Tải dữ liệu ---
    def _load_combined_training_data(self):
        """Tải dữ liệu training (cả wins và losses) từ một file JSON duy nhất."""
        path = self.training_data_path
        print(f"Logic V4: Loading combined data from JSON: {path}...")
        # Khởi tạo trước khi tải
        self.ai_winning_moves = defaultdict(default_win_entry)
        self.losing_moves_data = defaultdict(default_losing_moves_entry)
        self.load_error = None
        combined_data_json = {}

        if not path or not os.path.exists(path):
            self.load_error = f"File not found: '{path}'"
            print(f"Logic V4: {self.load_error}. Starting with empty data.")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                combined_data_json = json.load(f)

            if not isinstance(combined_data_json, dict):
                self.load_error = f"Invalid root JSON format (not dict) in {path}"
                print(f"Logic V4: {self.load_error}. Starting with empty data.")
                return

            # --- Tải AI Wins (Key JSON: "recorded_ai_wins") ---
            wins_json = combined_data_json.get('recorded_ai_wins', {}) # Lấy phần wins
            if isinstance(wins_json, dict):
                print(f"Logic V4: Converting {len(wins_json)} 'AI Wins' records (Board Size: {self.board_size})...")
                win_conv_err = 0; win_ok = 0
                for string_key, move_list in wins_json.items():
                    # *** Gọi instance method để chuyển đổi key ***
                    state_tuple = self.string_key_to_board_tuple(string_key)
                    if state_tuple and isinstance(move_list, list) and len(move_list) == 2:
                        try:
                            # Chuyển move list [r, c] thành tuple (r, c)
                            move_tuple = (int(move_list[0]), int(move_list[1]))
                            self.ai_winning_moves[state_tuple] = move_tuple # Lưu vào dict
                            win_ok += 1
                        except (ValueError, TypeError): win_conv_err += 1
                    else: win_conv_err += 1
                print(f"Logic V4: 'AI Wins' loaded. OK: {win_ok}. Errors: {win_conv_err}")
                if win_conv_err > 0 and not self.load_error:
                    self.load_error = f"{win_conv_err} AI Wins errors."
            else:
                print(f"Logic Warning: 'recorded_ai_wins' key not found or not a dict in {path}. Skipping AI Wins.")

            # --- Tải Losses (Key JSON: "learned_losses") ---
            losses_json = combined_data_json.get('learned_losses', {}) # Lấy phần losses
            if isinstance(losses_json, dict):
                print(f"Logic V4: Converting {len(losses_json)} 'Losses' records (Board Size: {self.board_size})...")
                loss_conv_err=0; loss_states_ok=0; loss_moves_ok=0
                for string_key, moves_list_outer in losses_json.items():
                    # *** Gọi instance method để chuyển đổi key ***
                    state_tuple = self.string_key_to_board_tuple(string_key)
                    # Value phải là list các nước đi thua (mỗi nước đi là list [r, c])
                    if state_tuple and isinstance(moves_list_outer, list):
                        current_losses = set() # Dùng set để lưu trong bộ nhớ
                        for move_list in moves_list_outer:
                            # Kiểm tra mỗi nước đi thua
                            if isinstance(move_list, list) and len(move_list) == 2:
                                try:
                                    # Chuyển list [r, c] thành tuple (r, c)
                                    move_tuple = (int(move_list[0]), int(move_list[1]))
                                    current_losses.add(move_tuple)
                                    loss_moves_ok += 1
                                except (ValueError, TypeError): loss_conv_err += 1
                            else: loss_conv_err += 1 # Nước đi thua không phải list 2 phần tử
                        # Chỉ lưu nếu set không rỗng
                        if current_losses:
                            self.losing_moves_data[state_tuple] = current_losses
                            loss_states_ok += 1
                    else: loss_conv_err += 1 # Lỗi key hoặc value không phải list
                print(f"Logic V4: 'Losses' loaded. States: {loss_states_ok}, Moves: {loss_moves_ok}. Errors: {loss_conv_err}")
                if loss_conv_err > 0 and not self.load_error:
                    self.load_error = (self.load_error+"; " if self.load_error else "") + f"{loss_conv_err} Losses errors."
            else:
                print(f"Logic Warning: 'learned_losses' key not found or not a dict in {path}. Skipping Losses.")

        except json.JSONDecodeError as e:
            self.load_error = f"JSON Decode Err: {e}"; print(f"Logic V4: {self.load_error} in {path}.")
        except Exception as e:
            self.load_error = f"Unexpected load err: {e}"; print(f"Logic V4: {self.load_error} from {path}."); traceback.print_exc()

        # Đảm bảo dict tồn tại dù lỗi
        if self.ai_winning_moves is None: self.ai_winning_moves = defaultdict(default_win_entry)
        if self.losing_moves_data is None: self.losing_moves_data = defaultdict(default_losing_moves_entry)

    # --- Ghi nhận kết quả ---
    def record_winning_move(self, state_tuple, winning_move_tuple):
        """
        Ghi nhận nước đi thắng của AI cho một trạng thái.
        Trả về True nếu dữ liệu được thêm/cập nhật, False nếu không đổi.
        """
        if not hasattr(self, 'ai_winning_moves') or self.ai_winning_moves is None:
            print("Logic ERROR: record_winning_move: ai_winning_moves chưa khởi tạo."); return False
        if not isinstance(state_tuple, tuple) or not isinstance(winning_move_tuple, tuple) or len(winning_move_tuple) != 2:
            print(f"Logic ERROR: record_winning_move input invalid."); return False

        try:
            int_move = (int(winning_move_tuple[0]), int(winning_move_tuple[1]))
            current_move = self.ai_winning_moves.get(state_tuple) # Lấy nước đi hiện tại (nếu có)
            # Chỉ cập nhật nếu chưa có hoặc nước đi mới khác nước đi cũ
            if current_move != int_move:
                self.ai_winning_moves[state_tuple] = int_move
                print(f"Logic V4: Recorded AI winning move {int_move} for state.")
                return True # Dữ liệu đã thay đổi
            # print(f"Logic V4: AI winning move {int_move} already recorded for state. No change.")
            return False # Dữ liệu không thay đổi
        except (ValueError, TypeError):
            print(f"Logic Warning: Invalid move tuple in record_winning_move: {winning_move_tuple}"); return False

    def record_losing_moves(self, losing_state_move_pairs):
        """
        Ghi nhận các cặp (trạng thái, nước đi thua) của AI.
        Trả về True nếu có ít nhất một nước đi thua *mới* được thêm, False nếu không.
        """
        if not hasattr(self, 'losing_moves_data') or self.losing_moves_data is None:
            print("Logic ERROR: record_losing_moves: losing_moves_data chưa khởi tạo."); return False
        if not isinstance(losing_state_move_pairs, list):
            print(f"Logic ERROR: record_losing_moves input not list."); return False

        data_changed = False # Cờ báo có thay đổi không
        for item in losing_state_move_pairs:
            if isinstance(item, tuple) and len(item) == 2:
                state_tuple, move_tuple = item
                if isinstance(state_tuple, tuple) and isinstance(move_tuple, tuple) and len(move_tuple) == 2:
                    try:
                        int_move = (int(move_tuple[0]), int(move_tuple[1]))
                        # Lấy set hiện tại hoặc tạo mới nếu chưa có
                        current_losses = self.losing_moves_data.setdefault(state_tuple, set())
                        if int_move not in current_losses:
                            current_losses.add(int_move)
                            data_changed = True # Đánh dấu có thay đổi
                    except (ValueError, TypeError): print(f"Logic Warn: Invalid move in record_losing: {move_tuple}")
                else: print(f"Logic Warn: Invalid inner item type in record_losing: {item}")
            else: print(f"Logic Warn: Invalid item format in record_losing: {item}")

        if data_changed: print(f"Logic V4: Recorded new losing move(s).")
        return data_changed # Trả về cờ báo thay đổi


    # --- Logic Game cơ bản (is_valid_move, is_board_full, check_win, get_relevant_empty_cells) ---
    def _board_to_tuple(self, board):
        if isinstance(board, tuple): return board
        try: return tuple(tuple(row) for row in board)
        except TypeError: print("Logic ERROR: Board to tuple failed."); return None
    def is_valid_move(self, board, r, c):
        bounds = (0 <= r < self.board_size and 0 <= c < self.board_size)
        if not bounds: return False
        try: return r < len(board) and c < len(board[r]) and board[r][c] == EMPTY
        except: return False # Lỗi index hoặc type
    def is_board_full(self, board):
        try:
            for r in range(self.board_size):
                 if r >= len(board) or len(board[r]) < self.board_size: return False
                 if any(board[r][c] == EMPTY for c in range(self.board_size)): return False
            return True
        except: return False
    def check_win(self, board, player):
        try:
            for r in range(self.board_size):
                if r >= len(board) or len(board[r]) == 0: continue
                for c in range(self.board_size):
                    if c >= len(board[r]): continue
                    if board[r][c] == player:
                        for dr, dc in self.directions:
                            count = 0
                            for i in range(self.win_length):
                                nr, nc = r + i*dr, c + i*dc
                                if 0 <= nr < self.board_size and 0 <= nc < self.board_size and \
                                   nr < len(board) and nc < len(board[nr]) and board[nr][nc] == player: count += 1
                                else: break
                            if count == self.win_length: return True
            return False
        except: return False
    def get_relevant_empty_cells(self, board, distance=2):
        occupied = []
        try:
            rows = len(board);
            if rows == 0: return []
            for r in range(min(self.board_size, rows)):
                row_len = len(board[r])
                for c in range(min(self.board_size, row_len)):
                    if board[r][c] != EMPTY: occupied.append((r, c))
            if not occupied: # Bàn trống
                cr, cc = self.board_size // 2, self.board_size // 2
                if self.is_valid_move(board, cr, cc): return [(cr, cc)]
                potentials=sorted([(r,c) for r in range(max(0,cr-1),min(self.board_size,cr+2)) for c in range(max(0,cc-1),min(self.board_size,cc+2)) if (r,c)!=(cr,cc)],key=lambda p:max(abs(p[0]-cr),abs(p[1]-cc)))
                for nr, nc in potentials:
                    if self.is_valid_move(board, nr, nc): return [(nr, nc)]
                return []
            min_r=min(r for r,c in occupied); max_r=max(r for r,c in occupied)
            min_c=min(c for r,c in occupied); max_c=max(c for r,c in occupied)
            sr=max(0,min_r-distance); er=min(self.board_size,max_r+distance+1)
            sc=max(0,min_c-distance); ec=min(self.board_size,max_c+distance+1)
            relevant = set()
            for r in range(sr, er):
                if r >= rows: continue
                row_len = len(board[r])
                for c in range(sc, ec):
                    if c >= row_len: continue
                    if board[r][c] == EMPTY and any(max(abs(r-orow),abs(c-ocol))<=distance for orow,ocol in occupied):
                        relevant.add((r, c))
            if not relevant and not self.is_board_full(board): # Fallback nếu ko có ô gần
                 return [(r,c) for r in range(min(self.board_size, rows)) for c in range(min(self.board_size, len(board[r]))) if board[r][c] == EMPTY]
            return list(relevant)
        except Exception as e: print(f"ERR get_relevant: {e}"); return []

    # --- Đánh giá nước đi và các mẫu (evaluate_move, _analyze_patterns_at, _count_lines_with_pattern) ---
    # Các hàm này giữ nguyên logic tính điểm và phân tích mẫu từ V3/V4
    def evaluate_move(self, board, r, c, player):
        opponent = PLAYER_O if player == PLAYER_X else PLAYER_X
        temp_board = copy.deepcopy(board); temp_board[r][c] = player
        if self.check_win(temp_board, player): return SCORE_WIN, "WIN"
        # Attack score
        atk_score = 0; my_pats = self._analyze_patterns_at(temp_board, r, c, player)
        n_open3 = self._count_lines_with_pattern(temp_board, r, c, player, 'open3')
        if my_pats['open4']>0: atk_score=max(atk_score, SCORE_CREATE_OPEN_4)
        if n_open3>=2: atk_score=max(atk_score, SCORE_CREATE_FORK_OPEN3)
        if my_pats['half4']>0 and atk_score<SCORE_CREATE_HALF_OPEN_4: atk_score=max(atk_score, SCORE_CREATE_HALF_OPEN_4)
        if n_open3==1 and atk_score<SCORE_CREATE_OPEN_3: atk_score=max(atk_score, SCORE_CREATE_OPEN_3)
        if my_pats['half3']>0 and atk_score<SCORE_CREATE_HALF_OPEN_3: atk_score=max(atk_score, SCORE_CREATE_HALF_OPEN_3)
        if my_pats['open2']>0 and atk_score<SCORE_CREATE_OPEN_2: atk_score=max(atk_score, SCORE_CREATE_OPEN_2)
        if my_pats['half2']>0 and atk_score<SCORE_CREATE_HALF_OPEN_2: atk_score=max(atk_score, SCORE_CREATE_HALF_OPEN_2)
        # Defense score
        def_score = 0; temp_board[r][c] = opponent # Thử đặt quân địch
        if self.check_win(temp_board, opponent): def_score=max(def_score, SCORE_BLOCK_WIN)
        else:
            opp_pats=self._analyze_patterns_at(temp_board, r, c, opponent)
            opp_n_open3=self._count_lines_with_pattern(temp_board, r, c, opponent, 'open3')
            if opp_pats['open4']>0: def_score=max(def_score, SCORE_BLOCK_OPEN_4)
            if opp_n_open3>=2: def_score=max(def_score, SCORE_BLOCK_FORK)
            if opp_pats['half4']>0 and def_score<SCORE_BLOCK_HALF_OPEN_4: def_score=max(def_score, SCORE_BLOCK_HALF_OPEN_4)
            if opp_n_open3==1 and def_score<SCORE_BLOCK_OPEN_3: def_score=max(def_score, SCORE_BLOCK_OPEN_3)
            if opp_pats['half3']>0 and def_score<SCORE_BLOCK_HALF_OPEN_3: def_score=max(def_score, SCORE_BLOCK_HALF_OPEN_3)
            if opp_pats['open2']>0 and def_score<SCORE_BLOCK_OPEN_2: def_score=max(def_score, SCORE_BLOCK_OPEN_2)
            if opp_pats['half2']>0 and def_score<SCORE_BLOCK_HALF_OPEN_2: def_score=max(def_score, SCORE_BLOCK_HALF_OPEN_2)
        # Combine
        final_score = max(def_score, atk_score, SCORE_POSITIONAL)
        # Determine source
        src="HEURISTIC_POS"
        if final_score>=SCORE_BLOCK_WIN: src="BLOCK_WIN"
        elif final_score>=SCORE_BLOCK_OPEN_4: src="BLOCK_OPEN_4"
        elif final_score>=SCORE_BLOCK_OPEN_3: src="BLOCK_OPEN_3"
        elif final_score>=SCORE_CREATE_OPEN_4: src="CREATE_OPEN_4"
        elif final_score>=SCORE_CREATE_FORK_OPEN3: src="CREATE_FORK_OPEN3"
        elif final_score>=SCORE_BLOCK_FORK: src="BLOCK_FORK"
        elif final_score>=SCORE_CREATE_HALF_OPEN_4: src="CREATE_HALF_OPEN_4"
        elif final_score>=SCORE_BLOCK_HALF_OPEN_4: src="BLOCK_HALF_OPEN_4"
        elif final_score>=SCORE_CREATE_OPEN_3: src="CREATE_OPEN_3"
        elif final_score>=SCORE_BLOCK_HALF_OPEN_3: src="BLOCK_HALF_OPEN_3"
        elif final_score>=SCORE_CREATE_HALF_OPEN_3: src="CREATE_HALF_OPEN_3"
        elif final_score>=SCORE_BLOCK_OPEN_2: src="BLOCK_OPEN_2"
        elif final_score>=SCORE_CREATE_OPEN_2: src="CREATE_OPEN_2"
        elif final_score>SCORE_POSITIONAL: src="HEURISTIC_PATTERN"
        return final_score, src
    def _analyze_patterns_at(self, board, r, c, player):
        pats=defaultdict(int); opp=PLAYER_O if player==PLAYER_X else PLAYER_X
        if not(0<=r<len(board) and 0<=c<len(board[r])) or board[r][c]!=player: return pats
        for dr,dc in self.directions:
            line=[]; max_len=self.win_length+2
            for i in range(-(max_len-1), max_len):
                nr,nc=r+i*dr,c+i*dc
                if 0<=nr<self.board_size and 0<=nc<self.board_size and nr<len(board) and nc<len(board[nr]): line.append(board[nr][nc])
                else: line.append(None)
            ctr=max_len-1; llen=len(line); found={'open4':False,'half4':False}
            # Open 4
            if not found['open4']:
                for i in range(max(0,ctr-4),min(llen-5,ctr+1)):
                     if i+1<=ctr<=i+4:
                          seg=line[i:i+6]
                          if len(seg)==6 and seg[0]==EMPTY and all(p==player for p in seg[1:5]) and seg[5]==EMPTY: pats['open4']+=1; found['open4']=True; break
            # Half 4
            if not found['open4'] and not found['half4']:
                for i in range(max(0,ctr-4),min(llen-5,ctr+1)):
                     if i+1<=ctr<=i+4:
                          seg=line[i:i+6]
                          if len(seg)==6 and all(p==player for p in seg[1:5]):
                              half=(seg[0]==EMPTY and (seg[5]==opp or seg[5] is None)) or ((seg[0]==opp or seg[0] is None) and seg[5]==EMPTY)
                              if half: pats['half4']+=1; found['half4']=True; break
            # Open 3
            for i in range(max(0,ctr-3),min(llen-4,ctr+1)):
                 if i+1<=ctr<=i+3: seg=line[i:i+5];
                 if len(seg)==5 and seg[0]==EMPTY and all(p==player for p in seg[1:4]) and seg[4]==EMPTY: pats['open3']+=1
            # Half 3
            for i in range(max(0,ctr-3),min(llen-4,ctr+1)):
                 if i+1<=ctr<=i+3:
                     seg=line[i:i+5];
                     if len(seg)==5 and all(p==player for p in seg[1:4]):
                          half=(seg[0]==EMPTY and (seg[4]==opp or seg[4] is None)) or ((seg[0]==opp or seg[0] is None) and seg[4]==EMPTY)
                          if half: pats['half3']+=1
            # Open 2
            for i in range(max(0,ctr-2),min(llen-3,ctr+1)):
                 if i+1<=ctr<=i+2: seg=line[i:i+4];
                 if len(seg)==4 and seg[0]==EMPTY and all(p==player for p in seg[1:3]) and seg[3]==EMPTY: pats['open2']+=1
            # Half 2
            for i in range(max(0,ctr-2),min(llen-3,ctr+1)):
                 if i+1<=ctr<=i+2:
                     seg=line[i:i+4];
                     if len(seg)==4 and all(p==player for p in seg[1:3]):
                          half=(seg[0]==EMPTY and (seg[3]==opp or seg[3] is None)) or ((seg[0]==opp or seg[0] is None) and seg[3]==EMPTY)
                          if half: pats['half2']+=1
        return pats
    def _count_lines_with_pattern(self, board, r, c, player, pattern_type):
        count=0; opp=PLAYER_O if player==PLAYER_X else PLAYER_X
        if not(0<=r<len(board) and 0<=c<len(board[r])) or board[r][c]!=player: return 0
        for dr,dc in self.directions:
            line=[]; max_len=7;
            for i in range(-(max_len-1),max_len): nr,nc=r+i*dr,c+i*dc; line.append(board[nr][nc] if 0<=nr<self.board_size and 0<=nc<self.board_size and nr<len(board) and nc<len(board[nr]) else None)
            ctr=max_len-1; llen=len(line); found=False
            if pattern_type=='open3':
                for i in range(max(0,ctr-3),min(llen-4,ctr+1)):
                    if i+1<=ctr<=i+3: seg=line[i:i+5];
                    if len(seg)==5 and seg[0]==EMPTY and all(p==player for p in seg[1:4]) and seg[4]==EMPTY: found=True; break
            elif pattern_type=='half4':
                 for i in range(max(0,ctr-4),min(llen-5,ctr+1)):
                     if i+1<=ctr<=i+4: seg=line[i:i+6];
                     if len(seg)==6 and all(p==player for p in seg[1:5]): half=(seg[0]==EMPTY and (seg[5]==opp or seg[5] is None)) or ((seg[0]==opp or seg[0] is None) and seg[5]==EMPTY);
                     if half: found=True; break
            if found: count+=1
        return count

    # --- Tìm nước đi (find_novel_move, find_best_move) ---
    # Logic của các hàm này đã ổn định trong V4, giữ nguyên
    def find_novel_move(self, board, player):
        current_board = copy.deepcopy(board); board_tuple = self._board_to_tuple(current_board)
        learned_win_move = None; losing_moves = set()
        if self.ai_winning_moves is not None: learned_win_move = self.ai_winning_moves.get(board_tuple)
        if self.losing_moves_data is not None: losing_moves = self.losing_moves_data.get(board_tuple, set())

        possible = self.get_relevant_empty_cells(current_board, 1) or \
                   self.get_relevant_empty_cells(current_board, 2) or \
                   self.get_relevant_empty_cells(current_board, 3)
        if not possible: return None, "NO_MOVE"

        random.shuffle(possible); novel_move = None
        for r, c in possible:
            move = (r, c)
            if self.is_valid_move(current_board, r, c) and move != learned_win_move and move not in losing_moves:
                novel_move = move; break

        if novel_move: return novel_move, "FORCED_NOVEL"

        # Fallback
        fallback_move, fallback_src = self.find_best_move(board, player, use_training_data=False, force_explore=True)
        if fallback_move:
             if self.losing_moves_data and fallback_move in self.losing_moves_data.get(board_tuple, set()):
                 print(f"WARN: Novel fallback {fallback_move} is losing! Random avoid.")
                 valid_avoid = [m for m in possible if self.is_valid_move(current_board,m[0],m[1]) and m not in losing_moves]
                 if valid_avoid: return random.choice(valid_avoid), "RANDOM_AVOID_LOSS"
                 else: print("CRIT: All valid moves seem losing!"); return fallback_move, f"NOVEL_CALC_{fallback_src}_(WAS_LOSS)"
             else: return fallback_move, f"NOVEL_CALC_{fallback_src}"
        else:
            print("CRIT ERR: find_novel_move fallback failed.")
            final_valid = [(r,c) for r in range(self.board_size) for c in range(self.board_size) if self.is_valid_move(current_board,r,c)]
            if final_valid: return random.choice(final_valid), "ULTRA_FALLBACK_RANDOM"
            else: return None, "NOVEL_FALLBACK_FAILED"

    def find_best_move(self, board, player, use_training_data=None, force_explore=False):
        start_time = time.time(); opponent = PLAYER_O if player == PLAYER_X else PLAYER_X
        current_board = copy.deepcopy(board); board_tuple = self._board_to_tuple(current_board)
        attempt_use_data = self.use_training_data_setting if use_training_data is None else use_training_data

        possible = self.get_relevant_empty_cells(current_board, 1) or \
                   self.get_relevant_empty_cells(current_board, 2)
        if not possible:
             if self.is_board_full(current_board): return None, "NO_MOVE"
             else: possible = [(r,c) for r in range(self.board_size) for c in range(self.board_size) if self.is_valid_move(current_board,r,c)];
             if not possible: return None, "ERROR_NO_VALID_MOVE"

        known_losing = set();
        if self.losing_moves_data is not None: known_losing = self.losing_moves_data.get(board_tuple, set())

        # Ưu tiên 1&2: Thắng/Chặn thắng
        win_move=None; block_move=None; temp_board=copy.deepcopy(current_board)
        for r,c in possible:
            move=(r,c);
            if not self.is_valid_move(temp_board,r,c): continue
            temp_board[r][c]=player;
            if self.check_win(temp_board, player): win_move=move; temp_board[r][c]=EMPTY; break
            temp_board[r][c]=opponent;
            if self.check_win(temp_board, opponent):
                if block_move is None: block_move=move
            temp_board[r][c]=EMPTY;
        if win_move: return win_move, "WIN"
        if block_move: return block_move, "BLOCK_WIN"

        # Ưu tiên 3-5: Đánh giá điểm
        best_move=None; best_score=-math.inf; best_src="NONE"; evals={}
        moves_eval = [m for m in possible if m not in known_losing]
        if not moves_eval and possible:
             print(f"WARN: All {len(possible)} relevant moves known losses. Evaluating all."); moves_eval = possible
        if not moves_eval:
             print("ERR: No moves left to evaluate."); final_val = [(r,c) for r in range(self.board_size) for c in range(self.board_size) if self.is_valid_move(current_board,r,c)]
             if final_val: return random.choice(final_val), "RANDOM_LAST_RESORT"
             else: return None, "NO_MOVE"
        # Đánh giá
        for r,c in moves_eval:
             score,src = self.evaluate_move(current_board,r,c,player); evals[(r,c)]=(score,src)
             if score>best_score: best_score=score; best_move=(r,c); best_src=src

        # Xử lý force_explore / nước tốt nhất vẫn thua
        avoid_loss = bool(best_move and best_move in known_losing)
        if force_explore or avoid_loss:
             if avoid_loss: print(f"INFO: Best calc move {best_move} is known loss. Forcing novel.")
             else: print("INFO: Force explore. Forcing novel.")
             novel_m, novel_s = self.find_novel_move(current_board, player)
             if novel_m and novel_m != best_move: return novel_m, novel_s
             else: print(f"INFO: Novel move same/None. Using best_move: {best_move}")

        # Cân nhắc dữ liệu AI thắng đã ghi nhận (nếu không force/avoid)
        recorded_win_move = None
        # *** Sử dụng tên biến đã đổi: self.ai_winning_moves ***
        if attempt_use_data and not force_explore and not avoid_loss and self.ai_winning_moves is not None:
            recorded_win_tuple = self.ai_winning_moves.get(board_tuple)
            if recorded_win_tuple and isinstance(recorded_win_tuple, tuple) and len(recorded_win_tuple)==2:
                if recorded_win_tuple in known_losing: pass # Ko dùng nếu đã thua
                elif self.is_valid_move(current_board, recorded_win_tuple[0], recorded_win_tuple[1]):
                    rec_eval = evals.get(recorded_win_tuple)
                    if rec_eval:
                        rec_score,_=rec_eval; crit_thr=SCORE_BLOCK_OPEN_3; good_thr=SCORE_CREATE_OPEN_3
                        if best_score>=crit_thr and rec_score<crit_thr: pass
                        elif rec_score>=good_thr and rec_score>=best_score*0.7: recorded_win_move = recorded_win_tuple

        # Quyết định cuối cùng
        if recorded_win_move: return recorded_win_move, "LEARNED" # "LEARNED" dùng chung cho nước ghi nhận thắng
        elif best_move: # Dùng nước tốt nhất tính được
             final_src="HEURISTIC_POS" # Xác định lại source chuẩn
             if best_score>=SCORE_BLOCK_OPEN_4: final_src="BLOCK_OPEN_4"
             elif best_score>=SCORE_CREATE_OPEN_4: final_src="CREATE_OPEN_4"
             elif best_score>=SCORE_BLOCK_OPEN_3: final_src="BLOCK_OPEN_3"
             elif best_score>=SCORE_CREATE_FORK_OPEN3: final_src="CREATE_FORK_OPEN3"
             elif best_score>=SCORE_BLOCK_FORK: final_src="BLOCK_FORK"
             elif best_score>=SCORE_CREATE_HALF_OPEN_4: final_src="CREATE_HALF_OPEN_4"
             elif best_score>=SCORE_BLOCK_HALF_OPEN_4: final_src="BLOCK_HALF_OPEN_4"
             elif best_score>=SCORE_CREATE_OPEN_3: final_src="CREATE_OPEN_3"
             elif best_score>=SCORE_BLOCK_HALF_OPEN_3: final_src="BLOCK_HALF_OPEN_3"
             elif best_score>=SCORE_CREATE_HALF_OPEN_3: final_src="CREATE_HALF_OPEN_3"
             elif best_score>=SCORE_BLOCK_OPEN_2: final_src="BLOCK_OPEN_2"
             elif best_score>=SCORE_CREATE_OPEN_2: final_src="CREATE_OPEN_2"
             elif best_score>SCORE_POSITIONAL: final_src="HEURISTIC_PATTERN"
             return best_move, final_src
        else: # Fallback cuối cùng
            print("WARN V3: No best move found. Final Fallback.")
            final_fall = self.get_relevant_empty_cells(current_board, 3) or \
                         [(r,c) for r in range(self.board_size) for c in range(self.board_size) if self.is_valid_move(current_board,r,c)]
            opts = [m for m in final_fall if m not in known_losing]
            if not opts and final_fall: print("WARN: All final fallbacks losing."); opts = final_fall
            if opts: cr,cc=self.board_size//2,self.board_size//2; opts.sort(key=lambda m:max(abs(m[0]-cr),abs(m[1]-cc))); return opts[0], "DEFAULT_FALLBACK"
            elif self.is_board_full(current_board): return None, "NO_MOVE"
            else: print("CRIT ERR: No valid moves on non-full board."); return None, "ERROR_NO_MOVE_FOUND"

# --- END OF FILE caro_logic.py (V3 Score-Driven - Learns Win/Loss - AutoSave V4) ---