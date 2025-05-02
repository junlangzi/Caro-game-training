# --- START OF FILE train.py ---
# --- START OF FILE train.py (Size-Specific JSON Output - Fixed Import - V2) ---
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import threading
import time
import json
import random
import copy
import os
from collections import defaultdict
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import inspect

# Import logic
try:
    # *** SỬA LỖI IMPORT: Đổi tên thành default_win_entry ***
    from caro_logic import CaroLogic, PLAYER_X, PLAYER_O, EMPTY, default_win_entry, default_losing_moves_entry
except ImportError as e:
    print(f"LỖI IMPORT: Không tìm thấy caro_logic.py hoặc thiếu thành phần.\n{e}")
    messagebox.showerror("Lỗi Import", f"Lỗi import caro_logic.py:\n{e}")
    exit()
except Exception as e_other:
     print(f"LỖI IMPORT KHÁC: {e_other}")
     messagebox.showerror("Lỗi Import Khác", f"Lỗi import caro_logic:\n{e_other}")
     exit()


# --- Hàm trợ giúp (giữ nguyên) ---
def board_tuple_to_string_key(board_tuple):
    """Chuyển tuple bàn cờ thành chuỗi khóa cho JSON."""
    if not board_tuple or not isinstance(board_tuple, tuple): return ""
    try: return "".join("".join(str(cell) for cell in row) for row in board_tuple)
    except Exception: return ""

def string_key_to_board_tuple(string_key, board_size):
    """Chuyển chuỗi khóa JSON thành tuple bàn cờ."""
    if not isinstance(string_key, str) or not isinstance(board_size, int) or board_size <= 0: return None
    expected_len = board_size * board_size
    if len(string_key) != expected_len: return None
    try:
        rows = []
        for i in range(0, expected_len, board_size):
            rows.append(tuple(string_key[i:i+board_size]))
        return tuple(rows)
    except Exception: return None
# --- Kết thúc Hàm trợ giúp ---

class CaroTrainApp(ttkb.Window):
    def __init__(self):
        super().__init__(themename="litera")
        self.title("Huấn luyện AI Caro (Lưu JSON theo Kích thước) V2")
        self.geometry("700x750") # Kích thước cửa sổ

        # --- Cấu hình Training ---
        self.train_board_size = tk.IntVar(value=25)
        self.num_games_to_play = tk.IntVar(value=1000)
        default_threads = max(1, os.cpu_count() // 2 if os.cpu_count() else 1)
        self.num_threads = tk.IntVar(value=default_threads)
        self.epsilon = tk.DoubleVar(value=0.1)
        self.loop_limit = tk.IntVar(value=10)

        self.training_in_progress = False
        self.stop_training_flag = False
        self.current_training_data_path = ""

        # *** SỬA: Sử dụng tên biến nhất quán với logic ***
        self.ai_winning_moves_data = None # Dùng để lưu state -> winning_move
        self.losing_moves_data = None # Dùng để lưu state -> set of losing moves
        # Khóa dùng chung cho cả hai loại dữ liệu khi cần cập nhật đồng thời (hiếm khi)
        # Hoặc tạo khóa riêng nếu cần cập nhật độc lập thường xuyên
        self.training_data_lock = threading.Lock()

        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()

        self.after(0, self._initialize_ui_and_queues)

    def _initialize_ui_and_queues(self):
        """Khởi tạo UI và queues."""
        try:
            self._create_widgets()
            self._process_queues()
        except Exception as e:
            print(f"LỖI init UI/Queue: {e}"); traceback.print_exc()
            messagebox.showerror("Lỗi Khởi Tạo", f"Lỗi khởi tạo UI:\n{e}", parent=self)

    # --- Tải/Lưu JSON ---
    def _load_training_data(self):
        """Tải dữ liệu training (cả wins và losses) từ file JSON."""
        path = self.current_training_data_path
        if not path:
            self.log("Lỗi: Đường dẫn file training chưa được xác định.")
            # *** SỬA: Trả về dict chứa cả hai loại data rỗng ***
            return {'wins': defaultdict(default_win_entry), 'losses': defaultdict(default_losing_moves_entry)}

        self.log(f"Đang tải dữ liệu training từ JSON: {path}...")
        combined_data_json = {} # Dict tạm để đọc từ JSON

        # Khởi tạo dict rỗng trước khi tải
        loaded_wins = defaultdict(default_win_entry)
        loaded_losses = defaultdict(default_losing_moves_entry)

        if os.path.exists(path):
            try:
                start_time = time.time()
                with open(path, 'r', encoding='utf-8') as f:
                    combined_data_json = json.load(f)
                load_time = time.time() - start_time

                if not isinstance(combined_data_json, dict):
                    self.log(f"Lỗi: Dữ liệu gốc trong {path} không phải dict. Bắt đầu với data mới.")
                else:
                    self.log(f"Đã tải JSON ({load_time:.2f}s). Bắt đầu chuyển đổi...")
                    board_size = self.train_board_size.get()
                    if board_size <= 0:
                         self.log(f"Lỗi: Size bàn cờ {board_size} không hợp lệ. Ko thể chuyển đổi.")
                         return {'wins': loaded_wins, 'losses': loaded_losses}

                    # Chuyển đổi wins (key: "recorded_ai_wins")
                    wins_json = combined_data_json.get('recorded_ai_wins', {})
                    win_errors = 0
                    if isinstance(wins_json, dict):
                        for key, move_list in wins_json.items():
                            state = string_key_to_board_tuple(key, board_size)
                            if state and isinstance(move_list, list) and len(move_list) == 2:
                                try: loaded_wins[state] = (int(move_list[0]), int(move_list[1]))
                                except: win_errors += 1
                            else: win_errors += 1
                        self.log(f"  Wins loaded: {len(loaded_wins)}. Conversion errors: {win_errors}")
                    else: self.log("  Warning: 'recorded_ai_wins' not found or not a dict.")

                    # Chuyển đổi losses (key: "learned_losses")
                    losses_json = combined_data_json.get('learned_losses', {})
                    loss_errors = 0; loss_moves_count = 0
                    if isinstance(losses_json, dict):
                        for key, moves_outer_list in losses_json.items():
                            state = string_key_to_board_tuple(key, board_size)
                            if state and isinstance(moves_outer_list, list):
                                current_losses = set()
                                for move_list in moves_outer_list:
                                    if isinstance(move_list, list) and len(move_list) == 2:
                                        try: current_losses.add((int(move_list[0]), int(move_list[1]))); loss_moves_count += 1
                                        except: loss_errors += 1
                                    else: loss_errors += 1
                                if current_losses: loaded_losses[state] = current_losses
                            else: loss_errors += 1
                        self.log(f"  Losses loaded: {len(loaded_losses)} states, {loss_moves_count} moves. Conversion errors: {loss_errors}")
                    else: self.log("  Warning: 'learned_losses' not found or not a dict.")

            except json.JSONDecodeError as e: self.log(f"Lỗi giải mã JSON từ {path}: {e}. Bắt đầu data mới.")
            except Exception as e: self.log(f"Lỗi tải/phân tích JSON từ {path}: {e}"); traceback.print_exc()
        else:
             self.log(f"Không tìm thấy file {path}. Bắt đầu data mới.")

        # Trả về dict chứa cả hai loại data đã load
        return {'wins': loaded_wins, 'losses': loaded_losses}


    def _save_training_data_final(self):
        """Lưu cả dữ liệu wins và losses vào file JSON."""
        # *** SỬA: Kiểm tra cả hai loại dữ liệu ***
        if self.ai_winning_moves_data is None and self.losing_moves_data is None:
            self.log("Không có dữ liệu (wins/losses) trong bộ nhớ để lưu.")
            return
        path = self.current_training_data_path
        if not path:
            self.log("Lỗi: Đường dẫn file chưa được đặt. Không thể lưu.")
            return

        num_wins = len(self.ai_winning_moves_data) if self.ai_winning_moves_data else 0
        num_loss_states = len(self.losing_moves_data) if self.losing_moves_data else 0
        num_loss_moves = sum(len(v) for v in (self.losing_moves_data or {}).values())

        self.log(f"Chuẩn bị lưu vào JSON: {path} (Wins: {num_wins}, Loss States: {num_loss_states}, Loss Moves: {num_loss_moves})")

        json_wins = {}; json_losses = {}; errors = 0

        try:
            # Khóa để sao chép an toàn (nếu cần cập nhật song song, dù trainer thường ko làm vậy)
            with self.training_data_lock:
                wins_to_process = dict(self.ai_winning_moves_data or {})
                losses_to_process = dict(self.losing_moves_data or {})

            # Chuyển đổi wins
            for state, move in wins_to_process.items():
                key = board_tuple_to_string_key(state)
                if key and isinstance(move, tuple) and len(move) == 2:
                    try: json_wins[key] = [int(m) for m in move]
                    except: errors += 1
                else: errors += 1
            # Chuyển đổi losses
            for state, moves_set in losses_to_process.items():
                 key = board_tuple_to_string_key(state)
                 if key and isinstance(moves_set, set):
                     valid = [[int(m[0]),int(m[1])] for m in moves_set if isinstance(m,tuple) and len(m)==2]
                     if valid: json_losses[key] = valid
                 else: errors += 1

            if errors > 0: self.log(f"Cảnh báo: {errors} lỗi chuyển đổi JSON.")

            # Tạo cấu trúc JSON cuối cùng
            # *** SỬA: Sử dụng đúng key như trong logic load ***
            combined_data = {"recorded_ai_wins": json_wins, "learned_losses": json_losses}

            if not json_wins and not json_losses:
                 self.log("Không có bản ghi hợp lệ nào (wins/losses) để lưu.")
                 return

            self.log(f"Đang ghi vào {path}...")
            start_time = time.time()
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)

            # Ghi an toàn
            temp_path = path + ".tmp~"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False) # indent=2 cho gọn
            os.replace(temp_path, path)

            save_time = time.time() - start_time
            self.log(f"Đã lưu vào JSON thành công ({save_time:.2f}s).")

        except Exception as e:
            self.log(f"Lỗi nghiêm trọng khi chuyển đổi/lưu JSON vào {path}: {e}")
            traceback.print_exc()
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except Exception as rm_e: print(f"Ko thể xóa file tạm {temp_path}: {rm_e}")


    # --- GUI, Worker, Update, Manage ---
    def _create_widgets(self):
        """Tạo các thành phần giao diện."""
        main_frame = ttkb.Frame(self, padding=20); main_frame.pack(fill=BOTH, expand=YES)
        config_frame = ttkb.LabelFrame(main_frame, text="Cấu hình Huấn luyện", padding=15); config_frame.pack(fill=X, pady=10); config_frame.columnconfigure(1, weight=1)
        # Widgets trong config_frame (giữ nguyên)
        ttk.Label(config_frame, text="Kích thước bàn (NxN):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Spinbox(config_frame, from_=5, to=50, textvariable=self.train_board_size, width=5).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(config_frame, text="Số ván huấn luyện:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Spinbox(config_frame, from_=10, to=1000000, increment=100, textvariable=self.num_games_to_play, width=10).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(config_frame, text="Số luồng xử lý:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        max_thr = os.cpu_count() or 8; ttk.Spinbox(config_frame, from_=1, to=max_thr, textvariable=self.num_threads, width=5).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(config_frame, text="Tỷ lệ khám phá (Epsilon):").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        eps_scale = ttk.Scale(config_frame, from_=0.0, to=1.0, variable=self.epsilon, orient=tk.HORIZONTAL); eps_scale.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)
        self.epsilon_label = ttk.Label(config_frame, text=f"{self.epsilon.get():.2f}", width=4); self.epsilon_label.grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)
        eps_scale.configure(command=lambda v: self.epsilon_label.config(text=f"{float(v):.2f}"))
        ttk.Label(config_frame, text="Lượt đầu B chơi B.Thường (N):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Spinbox(config_frame, from_=0, to=100, textvariable=self.loop_limit, width=5).grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)

        # Khung điều khiển
        control_frame = ttkb.Frame(main_frame); control_frame.pack(fill=X, pady=10)
        self.start_button = ttkb.Button(control_frame, text="Bắt đầu", command=self.start_training, bootstyle=SUCCESS); self.start_button.pack(side=tk.LEFT, padx=10)
        self.stop_button = ttkb.Button(control_frame, text="Dừng", command=self.stop_training, bootstyle=DANGER, state=tk.DISABLED); self.stop_button.pack(side=tk.LEFT, padx=10)
        self.status_label = ttkb.Label(control_frame, text="Trạng thái: Sẵn sàng", anchor=tk.W); self.status_label.pack(side=tk.LEFT, padx=20, fill=X, expand=YES)

        # Thanh tiến trình và Log
        self.progress_bar = ttkb.Progressbar(main_frame, orient=tk.HORIZONTAL, length=300, mode='determinate'); self.progress_bar.pack(fill=X, pady=5)
        log_frame = ttkb.LabelFrame(main_frame, text="Log Huấn luyện", padding=10); log_frame.pack(fill=BOTH, expand=YES, pady=10)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=18, font=("Courier New", 9)); self.log_text.pack(fill=BOTH, expand=YES); self.log_text.config(state=tk.DISABLED)

    def log(self, message):
        if hasattr(self, 'log_queue'): self.log_queue.put(str(message))

    def update_status(self, message):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists(): self.after(0, lambda: self.status_label.config(text=f"Trạng thái: {message}"))

    def update_progress(self, value):
        if hasattr(self, 'progress_queue'): self.progress_queue.put(value)

    def _process_queues(self):
        try:
            logs = []; progs = []
            while not self.log_queue.empty(): logs.append(self.log_queue.get_nowait())
            while not self.progress_queue.empty(): progs.append(self.progress_queue.get_nowait())

            if logs and hasattr(self, 'log_text') and self.log_text.winfo_exists():
                 self.log_text.config(state=tk.NORMAL)
                 for msg in logs: self.log_text.insert(tk.END, msg + "\n")
                 self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)
            if progs and hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
                 self.progress_bar['value'] = progs[-1]
        except queue.Empty: pass
        except Exception as e: print(f"Lỗi xử lý queue: {e}"); traceback.print_exc()
        if self.training_in_progress or not self.log_queue.empty() or not self.progress_queue.empty():
             if self.winfo_exists(): self.after(100, self._process_queues)

    def _worker_play_one_game(self, game_id, board_size, logic_class, shared_data_ref, epsilon_value, loop_limit_value):
        """
        Chạy 1 ván game trong luồng worker.
        Trả về (winner, list_of_new_states).
        list_of_new_states = [(state_hash, move_tuple, player_who_made_move), ...]
        """
        try:
            # *** SỬA: Truyền dict chứa cả wins và losses ***
            logic_instance = logic_class(board_size, use_training_data=True, training_data_ref=shared_data_ref)
        except Exception as e:
            print(f"[Worker {game_id}] LỖI tạo Logic: {e}"); traceback.print_exc(); return ("ERROR", [])

        board = [[EMPTY for _ in range(board_size)] for _ in range(board_size)]
        player_A = PLAYER_X; player_B = PLAYER_O # Player B bị ép đi khác
        curr_p = random.choice([player_A, player_B])
        new_learned = [] # Lưu (state, move, player) mới học
        game_over = False; winner = None; turn = 0; MAX_TURNS = board_size * board_size + 5

        while not game_over and turn < MAX_TURNS:
            if self.stop_training_flag: return ("STOPPED", [])

            opponent = player_B if curr_p == player_A else player_A
            move = None; src = "INIT_ERR"; is_calculated = False
            board_hash = tuple(tuple(row) for row in board) # Key cho data
            explore = random.random() < epsilon_value

            try:
                if curr_p == player_A: # Player A chơi chuẩn (có explore)
                    res = logic_instance.find_best_move(board, curr_p, use_training_data=True, force_explore=explore)
                else: # Player B
                    if turn < loop_limit_value: # Chơi chuẩn lúc đầu
                        res = logic_instance.find_best_move(board, curr_p, use_training_data=True, force_explore=random.random()<epsilon_value)
                    else: # Bị ép đi mới lạ
                        res = logic_instance.find_novel_move(board, curr_p)

                if res: move, src = res; is_calculated = (src != "LEARNED") # Chỉ lưu nước ko phải LEARNED
                else: move, src = None, "NO_MOVE"

            except Exception as e: print(f"[W{game_id} T{turn} P{curr_p}] LỖI tìm nước: {e}"); traceback.print_exc(); move, src = None, "FIND_MOVE_EXC"

            # Thực hiện nước đi
            if move:
                r, c = move
                if 0 <= r < board_size and 0 <= c < board_size and board[r][c] == EMPTY:
                    if is_calculated: new_learned.append((board_hash, move, curr_p)) # Ghi nhận để học
                    board[r][c] = curr_p # Đặt quân
                    # Kiểm tra kết thúc
                    if logic_instance.check_win(board, curr_p): winner=curr_p; game_over=True
                    elif logic_instance.is_board_full(board): winner=None; game_over=True
                    else: curr_p = opponent # Chuyển lượt
                else: # Nước đi ko hợp lệ từ logic -> lỗi
                    print(f"[W{game_id} T{turn} P{curr_p}] LỖI NGHIÊM TRỌNG: Move ko hợp lệ {move} (Src: {src}). Xử thua.")
                    winner=opponent; game_over=True
            else: # Ko tìm thấy nước đi -> kết thúc
                winner = opponent if not logic_instance.is_board_full(board) else None; game_over=True

            turn += 1
            if turn >= MAX_TURNS and not game_over: print(f"[W{game_id}] Vượt quá lượt. Hòa."); winner=None; game_over=True

        return (winner, new_learned)

    def _update_shared_data(self, game_results_batch):
        """Cập nhật dữ liệu dùng chung (chỉ cập nhật ai_winning_moves)."""
        # *** SỬA: Chỉ cập nhật ai_winning_moves từ trainer ***
        # Dữ liệu losing_moves sẽ được học từ game chính
        # Kiểm tra xem dict wins có tồn tại không
        if self.ai_winning_moves_data is None:
            self.log("Cảnh báo: _update_shared_data: ai_winning_moves_data là None.")
            return 0

        updates_count = 0
        with self.training_data_lock: # Khóa để an toàn
            for _, (winner, newly_learned_states) in enumerate(game_results_batch):
                if winner == "ERROR" or winner == "STOPPED": continue
                # Chỉ ghi nhận nước đi của người thắng cuộc (giả định AI thắng khi học)
                # hoặc các nước đi mới lạ không dẫn đến thua ngay lập tức
                last_move_info = None
                if newly_learned_states:
                     last_move_info = newly_learned_states[-1] # Lấy nước đi cuối cùng trong list học được

                # Ghi nhận nếu AI thắng (hoặc ván hòa nhưng có nước đi tính toán cuối)
                if winner == PLAYER_X or winner == PLAYER_O: # Chỉ ghi khi có người thắng rõ ràng
                    # Tìm nước đi cuối cùng của người thắng
                    winning_player = winner
                    final_state = None
                    final_move = None
                    for state, move, player in reversed(newly_learned_states):
                         if player == winning_player:
                              # Tìm trạng thái *trước* nước đi thắng
                              # Cái này hơi phức tạp, trainer hiện tại đang lưu (state, move)
                              # Ta cần tìm trạng thái S sao cho đi M từ S dẫn đến thắng.
                              # Cách đơn giản nhất là lưu nước đi tính toán cuối cùng của người thắng
                              final_move = move
                              final_state = state # Trạng thái trước khi đi nước thắng
                              break
                    if final_state and final_move:
                         # Chỉ ghi nếu nước đi đó khác nước đi đã có
                         current_saved_move = self.ai_winning_moves_data.get(final_state)
                         if current_saved_move != final_move:
                              self.ai_winning_moves_data[final_state] = final_move
                              updates_count += 1

        return updates_count # Trả về số lượng cập nhật (chỉ win)


    def _manage_training(self, board_size, total_games, num_workers, logic_class, epsilon_value, loop_limit_value):
        """Luồng quản lý huấn luyện."""
        print("[Manager] Starting training management...")
        self.update_status(f"Bắt đầu {total_games} ván ({num_workers} luồng)...")
        games_done = 0; winsX = 0; winsO = 0; draws = 0; stopped_err = 0
        results_batch = [] # Lô kết quả chờ xử lý
        BATCH_SIZE = max(num_workers * 2, 20)
        total_updates = 0

        # *** SỬA: Tạo dict chứa cả hai loại data để truyền cho worker ***
        shared_data = {
            'wins': self.ai_winning_moves_data,
            'losses': self.losing_moves_data # Worker có thể cần đọc cái này để tránh đi vào nước thua đã biết
        }
        print(f"[Manager] Initial data size: Wins={len(shared_data['wins'])}, Losses={len(shared_data['losses'])}")

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            print(f"[Manager] Submitting {total_games} game tasks...")
            futures = {executor.submit(self._worker_play_one_game, i+1, board_size, logic_class, shared_data, epsilon_value, loop_limit_value): i+1 for i in range(total_games)}
            print("[Manager] Tasks submitted. Waiting for completion...")

            try:
                for future in as_completed(futures):
                    game_id = futures[future]
                    if self.stop_training_flag: stopped_err += 1; continue # Dừng sớm

                    try:
                        result = future.result(); results_batch.append(result); games_done += 1
                        winner, _ = result
                        if winner == PLAYER_X: winsX += 1
                        elif winner == PLAYER_O: winsO += 1
                        elif winner is None: draws += 1
                        else: stopped_err += 1 # ERROR or STOPPED

                        # Cập nhật data dùng chung theo lô
                        if len(results_batch) >= BATCH_SIZE or games_done == total_games:
                             updates = self._update_shared_data(results_batch) # Chỉ cập nhật wins
                             total_updates += updates; results_batch = []
                             self.update_progress(games_done)
                             self.update_status(f"Running... ({games_done}/{total_games}) Data Updates: {total_updates}")
                    except Exception as e: print(f'[Manager] ERROR processing game {game_id}: {e}'); traceback.print_exc(); stopped_err += 1
            except KeyboardInterrupt: print("[Manager] Ctrl+C detected!"); self.stop_training_flag = True
            finally: print("[Manager] Exiting as_completed loop.")

        print("[Manager] Main training loop finished.")
        # Xử lý lô cuối
        if results_batch:
            print("[Manager] Processing final batch..."); updates = self._update_shared_data(results_batch); total_updates += updates; print(f"[Manager] Updates from final batch: {updates}")

        # Log tổng kết
        games_ok = winsX + winsO + draws
        self.log(f"\n--- TRAINING SUMMARY ({'Stopped' if self.stop_training_flag else 'Completed'}) ---")
        self.log(f"Games processed (futures returned): {games_done}")
        self.log(f"Games finished (X/O/Draw): {games_ok}")
        if games_ok > 0:
            self.log(f"  - X Wins: {winsX} ({(winsX/games_ok*100):.1f}%)")
            self.log(f"  - O Wins: {winsO} ({(winsO/games_ok*100):.1f}%)")
            self.log(f"  - Draws:  {draws} ({(draws/games_ok*100):.1f}%)")
        self.log(f"Total AI win moves recorded/updated: {total_updates}")
        # *** SỬA: Log kích thước của cả hai loại data ***
        final_wins = len(self.ai_winning_moves_data) if self.ai_winning_moves_data else 0
        final_losses = len(self.losing_moves_data) if self.losing_moves_data else 0
        self.log(f"Final data size (in memory): Wins={final_wins}, Losses={final_losses}")
        if stopped_err > 0: self.log(f"Stopped/Errored games: {stopped_err}")

        # Gọi hàm hoàn tất trên GUI
        if self.winfo_exists(): self.after(100, self._training_finished)
        print("[Manager] Training management ended.")

    def start_training(self):
        """Bắt đầu huấn luyện."""
        if self.training_in_progress: messagebox.showwarning("Đang chạy", "Huấn luyện đang chạy.", parent=self); return

        board_size = self.train_board_size.get()
        if board_size < 5: messagebox.showerror("Lỗi", f"Size bàn {board_size} quá nhỏ (>=5).", parent=self); return

        self.current_training_data_path = f"data-{board_size}.json"; print(f"Training data path set to: {self.current_training_data_path}")

        self.training_in_progress = True; self.stop_training_flag = False
        self.start_button.config(state=tk.DISABLED); self.stop_button.config(state=tk.NORMAL)

        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state=tk.NORMAL); self.log_text.delete('1.0', tk.END); self.log_text.config(state=tk.DISABLED)
        self.update_status("Đang tải dữ liệu..."); self.update()

        # *** SỬA: Tải cả hai loại data ***
        loaded_data = self._load_training_data()
        self.ai_winning_moves_data = loaded_data['wins']
        self.losing_moves_data = loaded_data['losses']
        if self.ai_winning_moves_data is None or self.losing_moves_data is None:
             self.log("LỖI NGHIÊM TRỌNG: Không thể khởi tạo data."); self._training_finished(); return

        num_games=self.num_games_to_play.get(); num_workers=self.num_threads.get()
        eps=self.epsilon.get(); loop_lim=self.loop_limit.get()

        if hasattr(self,'progress_bar') and self.progress_bar.winfo_exists(): self.progress_bar['maximum']=num_games; self.progress_bar['value']=0
        if self.winfo_exists(): self.after(100, self._process_queues) # Bắt đầu xử lý queue

        self.log(f"--- START TRAINING ({os.path.basename(self.current_training_data_path)}) ---")
        self.log(f"Config: Board={board_size}x{board_size}, Games={num_games}, Threads={num_workers}, Epsilon={eps:.2f}, B Limit={loop_lim}")
        self.log(f"Initial data size: Wins={len(self.ai_winning_moves_data)}, Losses={len(self.losing_moves_data)}")
        self.update_status("Khởi chạy workers...")

        # *** SỬA: Truyền dict data cho luồng quản lý ***
        manager_thread = threading.Thread(target=self._manage_training, args=(board_size, num_games, num_workers, CaroLogic, eps, loop_lim), daemon=True)
        manager_thread.start()

    def stop_training(self):
        """Dừng huấn luyện."""
        if not self.training_in_progress: return
        self.log(">>> Yêu cầu dừng..."); self.update_status("Đang dừng...")
        self.stop_training_flag = True; self.stop_button.config(state=tk.DISABLED)

    def _training_finished(self):
        """Hàm gọi lại khi huấn luyện kết thúc."""
        print("[GUI] Training finished callback.")
        self.training_in_progress = False

        if hasattr(self, 'start_button') and self.start_button.winfo_exists(): self.start_button.config(state=tk.NORMAL)
        if hasattr(self, 'stop_button') and self.stop_button.winfo_exists(): self.stop_button.config(state=tk.DISABLED)

        should_save = False; final_status = ""
        # Chỉ hỏi lưu nếu bị dừng thủ công và có dữ liệu
        if self.stop_training_flag:
            # *** SỬA: Kiểm tra cả hai loại data ***
            if (self.ai_winning_moves_data and len(self.ai_winning_moves_data) > 0) or \
               (self.losing_moves_data and len(self.losing_moves_data) > 0):
                 if messagebox.askyesno("Lưu dữ liệu?", "Huấn luyện dừng. Lưu dữ liệu đã học?", parent=self):
                      should_save = True; final_status = "Đang lưu (sau khi dừng)..."
                 else: final_status = "Đã dừng (Không lưu)."
            else: final_status = "Đã dừng (Không có data)."
        else: # Hoàn thành bình thường -> luôn lưu
            should_save = True; final_status = "Hoàn tất. Đang lưu..."

        if should_save:
             self.update_status(final_status); self.update()
             save_thread = threading.Thread(target=self._save_training_data_final, daemon=True); save_thread.start()
             self.log("Bắt đầu lưu data trong nền...")
             # Cập nhật trạng thái cuối cùng (ko chờ lưu xong)
             if self.stop_training_flag: self.update_status("Đã dừng (Đang lưu...).")
             else: self.update_status("Hoàn tất (Đang lưu...).")
        else: self.update_status(final_status)

        if self.winfo_exists(): self.after(100, self._process_queues) # Xử lý log cuối

# --- Kiểm tra chữ ký Logic V4 ---
def check_logic_signatures():
    logic_ok = True; missing = []
    try:
        sig_init = inspect.signature(CaroLogic.__init__); req_init = {'self','board_size','training_data_path','use_training_data','training_data_ref'};
        if not req_init.issubset(set(sig_init.parameters.keys())): missing.append(f"__init__ thiếu: {req_init-set(sig_init.parameters.keys())}"); logic_ok=False
        sig_find = inspect.signature(CaroLogic.find_best_move); req_find = {'self','board','player','use_training_data','force_explore'};
        if not req_find.issubset(set(sig_find.parameters.keys())): missing.append(f"find_best_move thiếu: {req_find-set(sig_find.parameters.keys())}"); logic_ok=False
        if not hasattr(CaroLogic,'find_novel_move') or not callable(getattr(CaroLogic,'find_novel_move')): missing.append("thiếu hàm find_novel_move"); logic_ok=False
        else: sig_novel=inspect.signature(CaroLogic.find_novel_move); req_novel={'self','board','player'};
        if not req_novel.issubset(set(sig_novel.parameters.keys())): missing.append(f"find_novel_move thiếu: {req_novel-set(sig_novel.parameters.keys())}"); logic_ok=False
        # *** SỬA: Kiểm tra hàm record mới của V4 ***
        if not hasattr(CaroLogic,'record_winning_move'): missing.append("thiếu hàm record_winning_move"); logic_ok=False
        else: sig_rec_win=inspect.signature(CaroLogic.record_winning_move); req_rec_win={'self','state_tuple','winning_move_tuple'};
        if not req_rec_win.issubset(set(sig_rec_win.parameters.keys())): missing.append(f"record_winning_move thiếu: {req_rec_win-set(sig_rec_win.parameters.keys())}"); logic_ok=False
        if not hasattr(CaroLogic,'record_losing_moves'): missing.append("thiếu hàm record_losing_moves"); logic_ok=False
        else: sig_rec_loss=inspect.signature(CaroLogic.record_losing_moves); req_rec_loss={'self','losing_state_move_pairs'};
        if not req_rec_loss.issubset(set(sig_rec_loss.parameters.keys())): missing.append(f"record_losing_moves thiếu: {req_rec_loss-set(sig_rec_loss.parameters.keys())}"); logic_ok=False

        if not logic_ok: messagebox.showerror("Lỗi Chữ Ký Logic", "Cập nhật caro_logic.py:\n" + "\n".join(missing))
    except Exception as e: messagebox.showerror("Lỗi Kiểm Tra Logic", f"Lỗi kiểm tra CaroLogic: {e}"); logic_ok=False
    return logic_ok

# --- Chạy App ---
if __name__ == "__main__":
    if not check_logic_signatures(): print("LỖI: Chữ ký hàm caro_logic.py không đúng.")
    else:
        print("Chữ ký hàm CaroLogic hợp lệ.")
        try: app = CaroTrainApp(); app.mainloop()
        except Exception as main_e: print("LỖI CHẠY APP:"); traceback.print_exc(); messagebox.showerror("Lỗi nghiêm trọng", f"Lỗi:\n{main_e}")

# --- END OF FILE train.py (Size-Specific JSON Output - Fixed Import - V2) ---