# --- START OF FILE caro.py ---
# --- START OF FILE caro.py (Learn Win/Loss - Always Record New Data - AutoSave - V5) ---

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import threading
import time
import copy
import os
import json
from collections import defaultdict
import traceback
import inspect

# Import logic - Đảm bảo caro_logic.py (V4) đã được cập nhật
try:
    # Sử dụng phiên bản logic đã chỉnh sửa gần nhất
    from caro_logic import CaroLogic, PLAYER_X, PLAYER_O, EMPTY, default_win_entry, default_losing_moves_entry
except ImportError as e:
    messagebox.showerror("Lỗi Import Logic", f"Lỗi import caro_logic.py:\n{e}\nKiểm tra file và cập nhật.")
    print(traceback.format_exc()); exit()
except Exception as e_other:
    messagebox.showerror("Lỗi Import Logic Khác", f"Lỗi import caro_logic:\n{e_other}"); print(traceback.format_exc()); exit()


class CaroApp(ttkb.Window):
    def __init__(self):
        """Khởi tạo ứng dụng Caro."""
        super().__init__(themename="litera")
        self.title("Caro Game AI (AutoSave) V5")
        self.geometry("1400x950")

        # --- Cấu hình game ---
        self.board_size_var = tk.IntVar(value=25)
        self.max_think_time_var = tk.IntVar(value=20)
        self.board_size = self.board_size_var.get()
        self.max_think_time = self.max_think_time_var.get()

        # --- Cấu hình AI ---
        self.use_training_data = tk.BooleanVar(value=True)
        self.training_data_path_var = tk.StringVar(value="")
        self.show_ai_info_var = tk.BooleanVar(value=False) # Mặc định tắt info

        # --- Trạng thái game ---
        self.cell_size = 30; self.padding = 20
        self.board_width = 0; self.board_height = 0
        self.logic = None; self.board = []
        self.current_player = PLAYER_X; self.game_over = False
        self.player_timer_value = self.max_think_time; self.ai_timer_value = self.max_think_time
        self.timer_id_player = None; self.timer_id_ai = None
        self.ai_thinking = False; self.last_ai_move = None; self.last_ai_move_source = ""
        self.first_move_made = False
        self.game_history = [] # List of (state_tuple, player, move_tuple)
        self.data_changed = False # Cờ báo cần lưu
        self._closing = False # Cờ kiểm soát đóng

        self.after(0, self._initialize_ui_and_game)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _initialize_ui_and_game(self):
        """Khởi tạo UI và game."""
        try:
            self._create_widgets()
            self.new_game()
            self._toggle_ai_info_visibility() # Đặt trạng thái hiển thị ban đầu
        except Exception as e:
            print(f"LỖI init UI/Game: {e}"); traceback.print_exc()
            messagebox.showerror("Lỗi Khởi Tạo", f"Lỗi khởi tạo game:\n{e}")

    def _calculate_layout(self):
        """Tính toán kích thước ô, bàn cờ."""
        try:
            self.update_idletasks()
            max_w = self.winfo_width() * 0.65; max_h = self.winfo_height() - 2*self.padding - 50
            size = max(1, self.board_size_var.get()); self.board_size = size
            cell_w = max(5, int(max_w / size)); cell_h = max(5, int(max_h / size))
            self.cell_size = min(cell_w, cell_h, 35)
            self.board_width = size * self.cell_size; self.board_height = size * self.cell_size
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                 self.canvas.config(width=self.board_width, height=self.board_height)
        except Exception as e:
            print(f"Lỗi _calculate_layout: {e}"); self.cell_size = 25 # Fallback
            self.board_width = self.board_size * self.cell_size; self.board_height = self.board_size * self.cell_size
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                 self.canvas.config(width=self.board_width, height=self.board_height)

    def _initialize_logic(self):
        """Khởi tạo hoặc tải lại CaroLogic."""
        print("-" * 20); print(f"Khởi tạo/Tải lại CaroLogic (Always Record V5):")
        self.board_size = self.board_size_var.get()
        if self.board_size < 5: self.board_size = 5; self.board_size_var.set(5)
        path = f"data-{self.board_size}.json"; self.training_data_path_var.set(path)
        use_data = self.use_training_data.get(); exists = os.path.exists(path)
        print(f"  Size={self.board_size}, UseData={use_data}, Path={path}, Exists={exists}")
        try:
            self.logic = CaroLogic(board_size=self.board_size, training_data_path=path, use_training_data=use_data)
            load_status = None
            if use_data:
                wins_ok = bool(self.logic.ai_winning_moves)
                losses_ok = bool(self.logic.losing_moves_data)
                if (wins_ok or losses_ok) and not self.logic.load_error: load_status = True
                elif self.logic.load_error: load_status = False
                elif not exists: load_status = False
            self.update_ai_settings_display(loaded=load_status, path=path)
        except Exception as e:
            print(f"Lỗi nghiêm trọng init Logic: {e}"); traceback.print_exc()
            messagebox.showerror("Lỗi Logic", f"Ko thể init logic AI:\n{e}", parent=self)
            self.use_training_data.set(False)
            try: self.logic = CaroLogic(board_size=self.board_size, use_training_data=False)
            except Exception as fallback_e: print(f"Lỗi fallback logic: {fallback_e}"); self.logic = None
            self.update_ai_settings_display(loaded=None)

    def _create_widgets(self):
        """Tạo tất cả các thành phần giao diện người dùng."""
        main_frame = ttkb.Frame(self, padding=self.padding)
        main_frame.pack(fill=BOTH, expand=YES)

        # --- Khung Bàn cờ (Trái) ---
        board_frame = ttkb.Frame(main_frame)
        board_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, self.padding))
        self.canvas = tk.Canvas(board_frame, bg='white', highlightthickness=1, highlightbackground="grey")
        self.canvas.pack(pady=5, anchor='center'); self.canvas.bind("<Button-1>", self.handle_click)
        self.after(50, self._calculate_layout) # Tính layout sau khi hiển thị

        # --- Khung Điều khiển (Phải) ---
        control_frame = ttkb.Frame(main_frame, width=350)
        control_frame.pack(side=RIGHT, fill=Y, padx=(self.padding // 2, 0)); control_frame.pack_propagate(False)

        # -- Khung Trạng thái & Thời gian --
        st_frame = ttkb.LabelFrame(control_frame, text="Trạng thái & Thời gian", padding=10)
        st_frame.pack(pady=5, fill=X)
        self.status_label = ttkb.Label(st_frame, text="...", font=("Helvetica", 11, "bold"), anchor=tk.W)
        self.status_label.pack(pady=(0, 5), fill=X)
        t_grid = ttkb.Frame(st_frame); t_grid.pack(fill=X); t_grid.columnconfigure(1, weight=1)
        ttkb.Label(t_grid, text="Người chơi:", width=11).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        # Sửa lỗi font và fg cho player timer label
        self.player_timer_label = ttkb.Label(t_grid, text=f"{self.max_think_time}s",
                                             font=("Helvetica", 12, "bold"), # Font hợp lệ
                                             foreground="blue")             # Dùng foreground
        self.player_timer_label.grid(row=0, column=1, sticky=tk.W)
        ttkb.Label(t_grid, text="Máy (O):", width=11).grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        # Sửa lỗi font và fg cho AI timer label
        self.ai_timer_label = ttkb.Label(t_grid, text=f"{self.max_think_time}s",
                                         font=("Helvetica", 12, "bold"), # Font hợp lệ
                                         foreground="red")             # Dùng foreground
        self.ai_timer_label.grid(row=1, column=1, sticky=tk.W)

        # -- Khung Điều khiển Game --
        gc_frame = ttkb.LabelFrame(control_frame, text="Điều khiển Game", padding=10)
        gc_frame.pack(pady=10, fill=X)
        self.new_game_button = ttkb.Button(gc_frame, text="Ván mới (F2)", command=self.new_game, bootstyle=SUCCESS)
        self.new_game_button.pack(pady=5, fill=X)
        self.bind("<F2>", lambda event: self.new_game())
        # Nút Lưu thủ công đã bị xóa
        self.show_ai_info_check = ttkb.Checkbutton(gc_frame, text="Hiện thông tin nước đi Máy", variable=self.show_ai_info_var, bootstyle="info-round-toggle", command=self._toggle_ai_info_visibility)
        self.show_ai_info_check.pack(pady=5, anchor=tk.W)

        # -- Khung Cài đặt Game --
        set_frame = ttkb.LabelFrame(control_frame, text="Cài đặt Game", padding=10)
        set_frame.pack(pady=5, fill=X); set_frame.columnconfigure(1, weight=1)
        ttk.Label(set_frame, text="Kích thước bàn:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(set_frame, from_=5, to=50, textvariable=self.board_size_var, width=5, command=self.apply_board_size_change).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(set_frame, text="TG suy nghĩ (s):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(set_frame, from_=5, to=300, increment=5, textvariable=self.max_think_time_var, width=5, command=self.apply_think_time_change).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # -- Khung Cài đặt AI --
        ai_set_frame = ttkb.LabelFrame(control_frame, text="Cài đặt AI (Máy)", padding=10) # Gán vào biến để dùng trong _toggle_ai_info_visibility
        ai_set_frame.pack(pady=10, fill=X)
        self.use_data_check = ttkb.Checkbutton(ai_set_frame, text="Sử dụng dữ liệu đã học (.json)", variable=self.use_training_data, bootstyle="primary", command=self.toggle_use_data)
        self.use_data_check.pack(anchor=tk.W, pady=(0, 5))
        f_sel_frame = ttkb.Frame(ai_set_frame); f_sel_frame.pack(fill=X, pady=(0, 5))
        self.browse_button = ttkb.Button(f_sel_frame, text="Chọn file .json", command=self.browse_data_file, bootstyle=INFO, width=12)
        self.browse_button.pack(side=tk.LEFT, padx=(0, 5))
        # Sửa lỗi fg cho data path label
        self.data_path_label = ttkb.Label(f_sel_frame,
                                          text=f"File: data-{self.board_size_var.get()}.json",
                                          anchor=tk.W,
                                          foreground="grey") # Dùng foreground
        self.data_path_label.pack(side=tk.LEFT, fill=X, expand=YES)

        # -- Khung Thông tin nước đi của Máy --
        self.ai_move_info_frame = ttkb.LabelFrame(control_frame, text="Thông tin nước đi của Máy", padding=10)
        # Pack frame ban đầu, _toggle_ai_info_visibility sẽ quản lý vị trí và hiển thị
        self.ai_move_info_frame.pack(pady=10, fill=X)
        self.ai_thinking_label = ttkb.Label(self.ai_move_info_frame, text="...", foreground="orange", font=("Helvetica", 10, "italic"))
        self.ai_thinking_label.pack_forget() # Ẩn ban đầu
        self.ai_move_source_label = ttkb.Label(self.ai_move_info_frame, text="Nguồn gốc: N/A", font=("Helvetica", 10))
        self.ai_move_source_label.pack(fill=X, pady=(5,0)) # Hiện ban đầu

        # Cập nhật hiển thị file data ban đầu (sau khi label đã được tạo)
        self.update_ai_settings_display(loaded=None, path=self.training_data_path_var.get())

    def _toggle_ai_info_visibility(self):
        """Ẩn/hiện khung thông tin AI."""
        if not hasattr(self, 'ai_move_info_frame'): return
        try:
            show = self.show_ai_info_var.get()
            frame = self.ai_move_info_frame
            if show:
                if not frame.winfo_ismapped():
                    # Tìm widget phù hợp để đặt frame sau nó
                    after_widget = ai_set_frame # Đặt sau khung cài đặt AI
                    frame.pack(pady=10, fill=X, after=after_widget)
                    if self.last_ai_move_source: self.update_ai_move_source_label(self.last_ai_move_source)
                    if self.last_ai_move and not self.game_over: self.draw_board()
            else:
                if frame.winfo_ismapped(): frame.pack_forget()
                self.canvas.delete("highlight")
        except NameError: # Xử lý nếu ai_set_frame chưa được định nghĩa khi gọi lần đầu
             if show and not frame.winfo_ismapped(): frame.pack(pady=10, fill=X)
             elif not show and frame.winfo_ismapped(): frame.pack_forget(); self.canvas.delete("highlight")
        except tk.TclError as e: print(f"TclError toggle AI info: {e}")
        except Exception as e: print(f"Error toggle AI info: {e}")

    def toggle_use_data(self):
        """Xử lý bật/tắt checkbox sử dụng dữ liệu."""
        use_data = self.use_training_data.get(); print(f"Use data setting: {use_data}")
        self.browse_button.config(state=tk.NORMAL if use_data else tk.DISABLED)
        self.update_ai_settings_display(loaded=None, path=self.training_data_path_var.get())
        messagebox.showinfo("Cài đặt AI", "Cài đặt dùng data đã đổi. Bắt đầu 'Ván mới' để áp dụng.", parent=self)

    def browse_data_file(self):
        """Mở hộp thoại chọn file JSON."""
        curr_path = self.training_data_path_var.get()
        init_dir = os.path.dirname(curr_path) if curr_path and os.path.exists(os.path.dirname(curr_path)) else "."
        fpath = filedialog.askopenfilename(title="Chọn file data JSON", initialdir=init_dir, filetypes=[("JSON","*.json"),("All","*.*")], parent=self)
        if fpath and fpath != self.training_data_path_var.get():
            self.training_data_path_var.set(fpath); print(f"Selected data file: {fpath}")
            try: # Cập nhật size
                name = os.path.basename(fpath)
                if name.startswith("data-") and name.endswith(".json"):
                    size = int(name[5:-5])
                    if 5 <= size <= 50 and size != self.board_size_var.get():
                        print(f"Auto-updating size to {size}"); self.board_size_var.set(size)
            except ValueError: print("Cannot parse size from filename.")
            self.update_ai_settings_display(loaded=None, path=fpath)
            messagebox.showinfo("File Data", f"Đã chọn file: '{os.path.basename(fpath)}'.\nBắt đầu 'Ván mới'.", parent=self)
            self.new_game() # Tự động ván mới

    def update_ai_settings_display(self, loaded, path=None):
        """Cập nhật label trạng thái file data."""
        use_data = self.use_training_data.get()
        curr_path = path if path else self.training_data_path_var.get() or f"data-{self.board_size_var.get()}.json"
        fname = os.path.basename(curr_path)
        if not hasattr(self, 'data_path_label'): return

        text = f"File: {fname} "; color = "grey"
        if use_data:
            self.browse_button.config(state=tk.NORMAL)
            if loaded is True:
                wins = len(self.logic.ai_winning_moves) if self.logic and self.logic.ai_winning_moves else 0
                losses = len(self.logic.losing_moves_data) if self.logic and self.logic.losing_moves_data else 0
                text += f"(Win: {wins}, Loss: {losses})"; color = "green"
            elif loaded is False:
                err = f" ({self.logic.load_error})" if self.logic and self.logic.load_error else " (Ko tìm thấy?)"
                text += f"(Lỗi tải{err})"; color = "red"
            else: text += "(Chưa kiểm tra)"
            self.data_path_label.config(text=text, foreground=color)
        else:
            self.browse_button.config(state=tk.DISABLED)
            self.data_path_label.config(text="Không sử dụng dữ liệu", foreground="grey")

    def apply_board_size_change(self):
        """Xử lý thay đổi kích thước bàn cờ."""
        new_size = self.board_size_var.get()
        if new_size != self.board_size:
            new_path = f"data-{new_size}.json"
            msg = f"Đổi size {new_size}x{new_size}? Sẽ bắt đầu ván mới, tải '{os.path.basename(new_path)}'."
            if messagebox.askyesno("Xác nhận", msg, icon='warning', parent=self):
                print(f"Size -> {new_size}. Data -> {new_path}")
                self.training_data_path_var.set(new_path); self.new_game()
            else: self.board_size_var.set(self.board_size) # Hoàn tác nếu hủy

    def apply_think_time_change(self):
        """Xử lý thay đổi thời gian suy nghĩ."""
        new_time = self.max_think_time_var.get()
        if new_time != self.max_think_time:
             print(f"Think time -> {new_time}s.")
             self.max_think_time = new_time
             if not self.game_over: # Chỉ cập nhật nếu game đang chạy
                 try: self.player_timer_label.config(text=f"{new_time}s"); self.ai_timer_label.config(text=f"{new_time}s")
                 except tk.TclError: pass # Bỏ qua nếu widget bị hủy
                 self.player_timer_value = new_time; self.ai_timer_value = new_time

    def draw_board(self):
        """Vẽ lại bàn cờ."""
        if self._closing or not hasattr(self, 'canvas') or not self.canvas.winfo_exists(): return
        try:
            self._calculate_layout(); self.canvas.delete("all")
            # Vẽ lưới
            for i in range(self.board_size + 1):
                x=y=i*self.cell_size; clr="#CCC" if i%5==0 else "#EEE"; w=2 if i%5==0 else 1
                self.canvas.create_line(0, y, self.board_width, y, fill=clr, width=w)
                self.canvas.create_line(x, 0, x, self.board_height, fill=clr, width=w)
            # Vẽ quân cờ
            if not self.board: return
            for r in range(self.board_size):
                if r >= len(self.board): continue
                for c in range(self.board_size):
                    if c >= len(self.board[r]): continue
                    if self.board[r][c] != EMPTY: self.draw_piece(r, c, self.board[r][c])
            # Vẽ highlight (nếu hiện info)
            if self.show_ai_info_var.get() and self.last_ai_move and not self.game_over:
                r, c = self.last_ai_move
                if 0 <= r < self.board_size and 0 <= c < self.board_size:
                    x0,y0=c*self.cell_size+2, r*self.cell_size+2; x1,y1=(c+1)*self.cell_size-2,(r+1)*self.cell_size-2
                    # Map màu đầy đủ
                    color_map = {"WIN":"gold","BLOCK_WIN":"orange","LEARNED":"purple","BLOCK_OPEN_4":"darkred","CREATE_OPEN_4":"blue","BLOCK_OPEN_3":"darkorange","CREATE_FORK_OPEN3":"cyan","BLOCK_FORK":"brown","CREATE_HALF_OPEN_4":"dodgerblue","BLOCK_HALF_OPEN_4":"firebrick","CREATE_OPEN_3":"green","BLOCK_HALF_OPEN_3":"sandybrown","CREATE_HALF_OPEN_3":"lightgreen","BLOCK_OPEN_2":"grey","CREATE_OPEN_2":"lightgrey","HEURISTIC_PATTERN":"darkgreen","HEURISTIC_POS":"darkseagreen","DEFAULT_FALLBACK":"dimgrey","FORCED_NOVEL":"magenta","NOVEL_CALC_WIN":"lightgoldenrod","NOVEL_CALC_BLOCK_WIN":"lightsalmon","NOVEL_CALC_BLOCK_OPEN_4":"indianred","NOVEL_CALC_CREATE_OPEN_4":"lightblue","NOVEL_CALC_BLOCK_OPEN_3":"coral","RANDOM_AVOID_LOSS":"pink","ULTRA_FALLBACK_RANDOM":"violet","ERROR":"black","INVALID":"black","NONE":"black","FIND_MOVE_EXC":"black","NO_MOVE":"black","NOVEL_FALLBACK_FAILED":"black","ERROR_NO_VALID_MOVE":"black","ERROR_NO_MOVE_FOUND":"black"}
                    src=self.last_ai_move_source; clr="red"
                    if isinstance(src, str) and src.startswith("NOVEL_CALC_"): base=src.replace("NOVEL_CALC_","").replace("_(WAS_LOSS)",""); clr=color_map.get(base,"magenta")
                    else: clr=color_map.get(src,"red")
                    self.canvas.create_rectangle(x0,y0,x1,y1,outline=clr,width=3,tags="highlight")
        except tk.TclError: pass
        except IndexError: print("Lỗi vẽ: Index.")
        except Exception as e: print(f"Lỗi vẽ bàn: {e}"); traceback.print_exc()

    def draw_piece(self, row, col, player):
        """Vẽ một quân cờ."""
        if self._closing: return
        try:
            x=col*self.cell_size+self.cell_size/2; y=row*self.cell_size+self.cell_size/2; r=self.cell_size*0.38; w=2
            if player==PLAYER_X: d=r; self.canvas.create_line(x-d,y-d,x+d,y+d,fill="#007bff",width=w); self.canvas.create_line(x-d,y+d,x+d,y-d,fill="#007bff",width=w)
            elif player==PLAYER_O: self.canvas.create_oval(x-r,y-r,x+r,y+r,outline="#dc3545",fill="#fff",width=w)
        except tk.TclError: pass
        except Exception as e: print(f"Lỗi vẽ quân ({row},{col}): {e}")

    def handle_click(self, event):
        """Xử lý click của người chơi."""
        if self._closing or self.game_over or self.current_player != PLAYER_X or self.ai_thinking: return
        if not (0 <= event.x < self.board_width and 0 <= event.y < self.board_height): return
        try:
            col=int(event.x//self.cell_size); row=int(event.y//self.cell_size)
            if 0<=row<self.board_size and 0<=col<self.board_size and row<len(self.board) and col<len(self.board[row]) and self.board[row][col]==EMPTY:
                if not self.first_move_made: print("Nước đi đầu tiên."); self.first_move_made=True
                if self.show_ai_info_var.get(): self.update_ai_move_source_label("N/A")
                self.last_ai_move_source=""
                # Ghi history
                if self.logic: state=self.logic._board_to_tuple(self.board)
                else: state=tuple(tuple(r) for r in self.board) # Fallback
                self.game_history.append((state, PLAYER_X, (row, col)))
                self.make_move(row, col, PLAYER_X)
        except Exception as e: print(f"Lỗi handle_click: {e}"); traceback.print_exc()

    def make_move(self, row, col, player, move_source="PLAYER"):
        """Thực hiện nước đi, cập nhật, vẽ, kiểm tra, ghi history."""
        if self._closing or self.game_over or not self.logic: return
        if not self.logic.is_valid_move(self.board, row, col): print(f"Invalid move: P{player} ({row},{col})"); return

        # Ghi history cho AI (trước khi thay đổi self.board)
        if player == PLAYER_O:
            try: state=self.logic._board_to_tuple(self.board); self.game_history.append((state, PLAYER_O, (row, col)))
            except Exception as e: print(f"Lỗi ghi history AI: {e}")

        try:
            self.board[row][col]=player; self.draw_piece(row, col, player) # Thực hiện và vẽ
            # Cập nhật info AI nếu cần
            if player == PLAYER_O:
                self.last_ai_move=(row, col); self.last_ai_move_source=move_source
                if self.show_ai_info_var.get(): self.update_ai_move_source_label(move_source); self.canvas.delete("highlight"); self.draw_board()
            else: # Người đi
                self.last_ai_move=None; self.last_ai_move_source=""
                if self.show_ai_info_var.get(): self.canvas.delete("highlight") # Xóa highlight nếu đang hiện

            # Dừng timer
            if player == PLAYER_X: self.stop_player_timer()
            else: self.stop_ai_timer()

            # Kiểm tra kết thúc
            if self.logic.check_win(self.board, player): winner="Người chơi (X)" if player==PLAYER_X else "Máy (O)"; self.end_game(f"{winner} thắng!")
            elif self.logic.is_board_full(self.board): self.end_game("Hòa!")
            else: self.switch_player() # Chuyển lượt
        except tk.TclError: pass # Bỏ qua lỗi nếu đang đóng
        except Exception as e: print(f"Lỗi make_move ({row},{col}) {player}: {e}"); traceback.print_exc()

    def switch_player(self):
        """Chuyển lượt và bắt đầu timer."""
        if self._closing or self.game_over: return
        try:
            if self.current_player==PLAYER_X: self.current_player=PLAYER_O; self.update_status_label(); self.start_ai_timer(); self.ai_move()
            else: self.current_player=PLAYER_X; self.update_status_label();
            if self.first_move_made: self.start_player_timer()
        except Exception as e: print(f"Lỗi switch_player: {e}"); traceback.print_exc()

    def ai_move(self):
        """Yêu cầu AI tính toán."""
        if self._closing or self.game_over or not self.logic: return
        self.ai_thinking = True
        if self.show_ai_info_var.get():
            if hasattr(self, 'ai_thinking_label'): self.ai_thinking_label.pack(fill=X)
            self.update_ai_move_source_label("Đang tính...")
        self.update()
        threading.Thread(target=self._ai_move_thread, daemon=True).start()

    def _ai_move_thread(self):
        """Luồng AI tìm nước đi."""
        start_t=time.time(); move=None; src="ERROR"
        try:
            if not self.logic: raise Exception("Logic None.")
            board_copy=copy.deepcopy(self.board); use_data=self.use_training_data.get()
            res=self.logic.find_best_move(board_copy, PLAYER_O, use_training_data=use_data, force_explore=False)
            if res: move, src = res
            else: move=None; src="NO_MOVE"
        except Exception as e: print(f"LỖI LUỒNG AI: {e}"); traceback.print_exc(); move=None; src="FIND_MOVE_EXC"
        finally:
            think_t=time.time()-start_t; print(f"AI (O) nghĩ: {think_t:.3f}s. Move: {move}, Source: {src}")
            if self.winfo_exists() and not self._closing:
                self.after(0, self._ai_move_finished, move, src, think_t)
            else: print("Cửa sổ đóng/đang đóng, bỏ qua kq AI.")

    def _ai_move_finished(self, move, move_source, think_time):
        """Xử lý kết quả từ luồng AI."""
        if self._closing: return
        self._hide_ai_thinking_label() # Luôn ẩn

        if not self.game_over: # Chỉ xử lý nếu game chưa xong
            if move: # Tìm được nước
                if think_time <= self.max_think_time + 0.5: self.finalize_ai_move(move, move_source)
                else: print("AI timeout."); self.handle_timeout(PLAYER_O)
            elif move_source == "NO_MOVE": print("AI hết nước."); self.end_game("Hòa (Máy hết nước)!")
            else: print(f"AI lỗi ({move_source})."); self.end_game(f"Lỗi AI ({move_source})")

    def finalize_ai_move(self, move, move_source):
        """Thực hiện nước đi AI trên luồng chính."""
        if self._closing or self.game_over: return
        if isinstance(move, tuple) and len(move) == 2: self.make_move(move[0], move[1], PLAYER_O, move_source)
        else: print(f"Lỗi finalize: move={move}"); self.end_game("Lỗi AI (Move ko hợp lệ)")

    def update_ai_move_source_label(self, source):
        """Cập nhật label nguồn gốc (chỉ khi hiện)."""
        if not self.show_ai_info_var.get() or not hasattr(self, 'ai_move_source_label') or not self.ai_move_source_label.winfo_exists(): return
        # Map nguồn sang text và màu (map đầy đủ)
        s_map={"WIN":"Thắng!","BLOCK_WIN":"Chặn Thắng!","LEARNED":"Kinh nghiệm","BLOCK_OPEN_4":"Chặn 4!","CREATE_OPEN_4":"Tạo 4!","BLOCK_OPEN_3":"Chặn 3!","CREATE_FORK_OPEN3":"Tạo Đôi 3!","BLOCK_FORK":"Chặn Đôi!","CREATE_HALF_OPEN_4":"Tạo 4(nửa)","BLOCK_HALF_OPEN_4":"Chặn 4(nửa)","CREATE_OPEN_3":"Tạo 3","BLOCK_HALF_OPEN_3":"Chặn 3(nửa)","CREATE_HALF_OPEN_3":"Tạo 3(nửa)","BLOCK_OPEN_2":"Chặn 2","CREATE_OPEN_2":"Tạo 2","HEURISTIC_PATTERN":"Mẫu yếu","HEURISTIC_POS":"Vị trí","DEFAULT_FALLBACK":"Dự phòng","FORCED_NOVEL":"Nước Mới!","NOVEL_CALC_WIN":"NM Thắng","NOVEL_CALC_BLOCK_WIN":"NM Chặn Thắng","NOVEL_CALC_BLOCK_OPEN_4":"NM Chặn 4","NOVEL_CALC_CREATE_OPEN_4":"NM Tạo 4","NOVEL_CALC_BLOCK_OPEN_3":"NM Chặn 3","RANDOM_AVOID_LOSS":"Random Tránh Thua","ULTRA_FALLBACK_RANDOM":"Random Cuối","ERROR":"Lỗi Logic","INVALID":"Ko Hợp lệ","FIND_MOVE_EXC":"Lỗi Tìm Nước","NONE":"Ko có","NO_MOVE":"Hết nước","NOVEL_FALLBACK_FAILED":"Lỗi Tìm Nước Mới","ERROR_NO_VALID_MOVE":"Lỗi Ko Nước","ERROR_NO_MOVE_FOUND":"Lỗi Ko Tìm","N/A":"N/A","Đang tính...":"Đang tính..."}
        c_map={"WIN":"gold","BLOCK_WIN":"orange","LEARNED":"purple","BLOCK_OPEN_4":"darkred","CREATE_OPEN_4":"blue","BLOCK_OPEN_3":"darkorange","CREATE_FORK_OPEN3":"cyan","BLOCK_FORK":"brown","CREATE_HALF_OPEN_4":"dodgerblue","BLOCK_HALF_OPEN_4":"firebrick","CREATE_OPEN_3":"green","BLOCK_HALF_OPEN_3":"sandybrown","CREATE_HALF_OPEN_3":"lightgreen","BLOCK_OPEN_2":"grey","CREATE_OPEN_2":"lightgrey","HEURISTIC_PATTERN":"darkgreen","HEURISTIC_POS":"darkseagreen","DEFAULT_FALLBACK":"dimgrey","FORCED_NOVEL":"magenta","NOVEL_CALC_WIN":"lightgoldenrod","NOVEL_CALC_BLOCK_WIN":"lightsalmon","NOVEL_CALC_BLOCK_OPEN_4":"indianred","NOVEL_CALC_CREATE_OPEN_4":"lightblue","NOVEL_CALC_BLOCK_OPEN_3":"coral","RANDOM_AVOID_LOSS":"pink","ULTRA_FALLBACK_RANDOM":"violet","ERROR":"black","INVALID":"black","FIND_MOVE_EXC":"black","NONE":"black","NO_MOVE":"black","NOVEL_FALLBACK_FAILED":"black","ERROR_NO_VALID_MOVE":"black","ERROR_NO_MOVE_FOUND":"black","N/A":"grey","Đang tính...":"grey"}
        txt=str(source); clr="black"
        if isinstance(source, str) and source.startswith("NOVEL_CALC_"): base=source.replace("NOVEL_CALC_","").replace("_(WAS_LOSS)",""); base_txt,_=s_map.get(base,(base,"")); base_clr=c_map.get(base,"magenta"); suf=" (Đã thua!)" if source.endswith("_(WAS_LOSS)") else ""; txt=f"NM ({base_txt}){suf}"; clr=base_clr
        elif isinstance(source, str) and source.endswith("_(WAS_LOSS)"): base=source.replace("_(WAS_LOSS)",""); base_txt,_=s_map.get(base,(base,"")); base_clr=c_map.get(base,"grey"); txt=f"{base_txt} (Đã thua!)"; clr=base_clr
        else: txt_m,clr_m=s_map.get(source,None),c_map.get(source,None);
        if txt_m: txt=txt_m;
        if clr_m: clr=clr_m;
        try: self.ai_move_source_label.config(text=f"Nguồn gốc: {txt}", foreground=clr)
        except tk.TclError: pass

    def _hide_ai_thinking_label(self):
        """Ẩn label thinking và reset cờ."""
        if hasattr(self, 'ai_thinking_label') and self.ai_thinking_label.winfo_exists() and self.ai_thinking_label.winfo_ismapped():
            try: self.ai_thinking_label.pack_forget()
            except tk.TclError: pass
        self.ai_thinking = False

    def update_status_label(self):
        """Cập nhật label lượt chơi."""
        if self._closing or not hasattr(self, 'status_label') or not self.status_label.winfo_exists(): return
        if not self.game_over: player="Người(X)" if self.current_player==PLAYER_X else "Máy(O)";
        try: self.status_label.config(text=f"Lượt của: {player}")
        except tk.TclError: pass

    # --- Logic Timer (Giữ nguyên) ---
    def start_player_timer(self): self.stop_player_timer(); self.player_timer_value = self.max_think_time; self.player_timer_label.config(text=f"{self.player_timer_value}s"); self._update_player_timer()
    def _update_player_timer(self):
        if self._closing or self.game_over or self.current_player != PLAYER_X: self.stop_player_timer(); return
        if self.player_timer_value > 0: self.player_timer_value -= 1; self.player_timer_label.config(text=f"{self.player_timer_value}s"); self.timer_id_player = self.after(1000, self._update_player_timer)
        else: self.handle_timeout(PLAYER_X)
    def stop_player_timer(self):
        if self.timer_id_player: self.after_cancel(self.timer_id_player); self.timer_id_player = None
    def start_ai_timer(self): self.stop_ai_timer(); self.ai_timer_value = self.max_think_time; self.ai_timer_label.config(text=f"{self.ai_timer_value}s"); self._update_ai_timer()
    def _update_ai_timer(self):
        if self._closing or self.game_over or self.current_player != PLAYER_O: self.stop_ai_timer(); return
        if self.ai_timer_value > 0: self.ai_timer_value -= 1; self.ai_timer_label.config(text=f"{self.ai_timer_value}s"); self.timer_id_ai = self.after(1000, self._update_ai_timer)
        else: self.handle_timeout(PLAYER_O)
    def stop_ai_timer(self):
        if self.timer_id_ai: self.after_cancel(self.timer_id_ai); self.timer_id_ai = None
    def handle_timeout(self, player):
        if self._closing or self.game_over: return
        winner=PLAYER_O if player==PLAYER_X else PLAYER_X; w_name="Máy(O)" if winner==PLAYER_O else "Người(X)"; l_name="Người(X)" if player==PLAYER_X else "Máy(O)"; print(f"Timeout! {player}."); self.end_game(f"{l_name} hết giờ! {w_name} thắng!")
    # --- Kết thúc Logic Timer ---

    def end_game(self, message):
        """Kết thúc ván, xử lý học hỏi và tự động lưu."""
        if self.game_over or self._closing: return
        print(f"Game Over: {message}"); self.game_over = True
        self.stop_player_timer(); self.stop_ai_timer(); self._hide_ai_thinking_label()
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            try: self.status_label.config(text=f"KẾT THÚC: {message}")
            except tk.TclError: pass

        # --- LUÔN THỬ GHI DỮ LIỆU KHI KẾT THÚC VÁN ---
        data_was_updated = False # Cờ cục bộ cho lần ghi này
        if self.logic:
            # 1. Nếu AI thắng: Ghi nước thắng cuối
            if "Máy (O) thắng" in message and self.game_history:
                last_ai_state = None; last_ai_move = None
                for state, player, move in reversed(self.game_history):
                    if player == PLAYER_O: last_ai_state = state; last_ai_move = move; break
                if last_ai_state and last_ai_move:
                     if self.logic.record_winning_move(last_ai_state, last_ai_move):
                          data_was_updated = True # Đánh dấu có thay đổi
                          self.data_changed = True # Đặt cờ chung cho ứng dụng

            # 2. Nếu Người thắng: Ghi các nước thua của AI
            elif "Người chơi (X) thắng" in message:
                if self.learn_from_human_win(): # Hàm này trả về True nếu có data mới
                     data_was_updated = True
                     self.data_changed = True

        # --- Tự động lưu nếu có thay đổi TRONG VÁN NÀY ---
        if data_was_updated:
            print("Dữ liệu mới được học, tự động lưu...")
            if self._save_learned_data_internal():
                print("Tự động lưu thành công.")
                # Không reset self.data_changed ở đây, để on_closing biết cần lưu không
            else:
                print("Tự động lưu thất bại!")
                # Có thể hiện cảnh báo nếu muốn
        # ----------------------------------------------

        # Hiển thị popup
        self.after(100, lambda: messagebox.showinfo("Kết thúc ván", message, parent=self))

    def learn_from_human_win(self):
        """Phân tích và ghi nhận nước thua của AI. Trả về True nếu có data mới."""
        if not self.logic or not self.game_history: print("Ko thể học: logic/history thiếu."); return False
        print("Người (X) thắng! Phân tích nước đi AI (O)...")
        losing_moves = []
        for item in self.game_history:
             if isinstance(item, tuple) and len(item)==3:
                 state, player, move = item
                 if player==PLAYER_O and isinstance(state,tuple) and isinstance(move,tuple): losing_moves.append((state,move))
        if losing_moves:
            print(f"Tìm thấy {len(losing_moves)} nước đi của AI.")
            try: return self.logic.record_losing_moves(losing_moves) # Trả về kết quả từ logic
            except Exception as e: print(f"Lỗi logic.record_losing_moves: {e}"); traceback.print_exc()
        else: print("Ko tìm thấy nước đi AI?")
        return False # Ko có gì mới

    def new_game(self):
        """Bắt đầu ván mới."""
        # Không hỏi lưu nữa
        print("-" * 20 + "\nBắt đầu ván mới!" + "-" * 20)
        self.game_over = False; self.stop_player_timer(); self.stop_ai_timer(); self._hide_ai_thinking_label()
        self.first_move_made = False; self.game_history = [] # Reset history

        self.board_size = self.board_size_var.get(); self.max_think_time = self.max_think_time_var.get()
        if self.board_size < 5: self.board_size = 5; self.board_size_var.set(5)

        self._initialize_logic(); # Tải lại logic/data
        if self.logic is None: messagebox.showerror("Lỗi", "Ko thể init logic."); return

        try: self.board = [[EMPTY for _ in range(self.board_size)] for _ in range(self.board_size)]
        except MemoryError: messagebox.showerror("Lỗi Bộ Nhớ", f"Ko đủ bộ nhớ {self.board_size}^2."); return
        except Exception as e: messagebox.showerror("Lỗi", f"Lỗi tạo bàn: {e}"); return

        self.current_player=PLAYER_X; self.last_ai_move=None; self.last_ai_move_source=""
        self.draw_board(); self.update_status_label()
        if self.show_ai_info_var.get(): self.update_ai_move_source_label("N/A")
        else: # Vẫn reset text của label dù nó bị ẩn
             if hasattr(self, 'ai_move_source_label'):
                 try: self.ai_move_source_label.config(text="Nguồn gốc: N/A")
                 except tk.TclError: pass


        self.player_timer_value=self.max_think_time; self.ai_timer_value=self.max_think_time
        try: self.player_timer_label.config(text=f"{self.max_think_time}s"); self.ai_timer_label.config(text=f"{self.max_think_time}s")
        except tk.TclError: pass

    # --- Lưu dữ liệu ---
    # Hàm lưu thủ công đã bị xóa

    def _save_learned_data_internal(self):
        """Hàm nội bộ thực hiện lưu dữ liệu vào JSON."""
        if self._closing: return False # Không lưu nếu đang đóng
        if not self.logic: print("Lỗi lưu: Logic None."); return False
        path = self.training_data_path_var.get()
        if not path: print("Lỗi lưu: Path ko hợp lệ."); return False

        wins_data = self.logic.ai_winning_moves; losses_data = self.logic.losing_moves_data
        if wins_data is None or losses_data is None: print("Lỗi lưu: Data trong logic None."); return False

        num_wins = len(wins_data); num_loss_states = len(losses_data)
        num_loss_moves = sum(len(v) for v in losses_data.values() if isinstance(v, set))
        print(f"Chuẩn bị lưu vào {path}: Wins={num_wins}, LossStates={num_loss_states}, LossMoves={num_loss_moves}")

        json_wins={}; json_losses={}; errors=0
        try:
            # Chuyển đổi AI Wins (key JSON: "recorded_ai_wins")
            for state, move in wins_data.items():
                key = self.logic.board_tuple_to_string_key(state)
                if key and isinstance(move, tuple) and len(move)==2:
                    try: json_wins[key]=[int(m) for m in move]
                    except: errors+=1
                else: errors+=1
            # Chuyển đổi Losses (key JSON: "learned_losses")
            for state, moves_set in losses_data.items():
                 key = self.logic.board_tuple_to_string_key(state)
                 if key and isinstance(moves_set, set):
                     valid=[[int(m[0]),int(m[1])] for m in moves_set if isinstance(m,tuple) and len(m)==2]
                     if valid: json_losses[key]=valid
                 else: errors+=1
            if errors > 0: print(f"Cảnh báo: {errors} lỗi chuyển đổi JSON.")

            combined = {"recorded_ai_wins": json_wins, "learned_losses": json_losses} # Key JSON chuẩn
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            temp_path = path + ".tmp~" # File tạm
            with open(temp_path, 'w', encoding='utf-8') as f: json.dump(combined, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, path) # Ghi đè an toàn
            print(f"Đã lưu vào {path} thành công.")
            return True
        except Exception as e:
            print(f"Lỗi nghiêm trọng khi lưu JSON: {e}"); traceback.print_exc()
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except Exception as rm_e: print(f"Ko thể xóa file tạm {temp_path}: {rm_e}")
            return False

    def on_closing(self):
        """Xử lý khi đóng cửa sổ."""
        if self._closing: return
        print("Đóng ứng dụng..."); self._closing = True
        self.stop_player_timer(); self.stop_ai_timer() # Dừng timer

        save_success = True
        if self.data_changed: # Chỉ lưu khi thoát nếu CÓ THAY ĐỔI CHƯA LƯU
            print("Dữ liệu thay đổi chưa lưu, thử lưu lần cuối...")
            if not self._save_learned_data_internal():
                 save_success = False; print("Lưu khi thoát thất bại!")
            else: print("Lưu khi thoát thành công."); self.data_changed = False # Reset cờ

        print("Thoát ứng dụng.")
        self.after(0, self.destroy) # Gọi destroy an toàn


# --- Kiểm tra chữ ký Logic và Chạy App ---
if __name__ == "__main__":
    try: # Kiểm tra Logic V4
        sig_init = inspect.signature(CaroLogic.__init__); req_init = {'self','board_size','training_data_path','use_training_data'};
        if not req_init.issubset(set(sig_init.parameters.keys())): raise AttributeError(f"Logic.__init__ thiếu: {req_init-set(sig_init.parameters.keys())}")
        sig_find = inspect.signature(CaroLogic.find_best_move); req_find = {'self','board','player','use_training_data','force_explore'};
        if not req_find.issubset(set(sig_find.parameters.keys())): raise AttributeError(f"Logic.find_best_move thiếu: {req_find-set(sig_find.parameters.keys())}")
        if not hasattr(CaroLogic, 'record_winning_move'): raise AttributeError("Logic thiếu 'record_winning_move'")
        sig_rec_win = inspect.signature(CaroLogic.record_winning_move); req_rec_win = {'self','state_tuple','winning_move_tuple'};
        if not req_rec_win.issubset(set(sig_rec_win.parameters.keys())): raise AttributeError(f"Logic.record_winning_move thiếu: {req_rec_win-set(sig_rec_win.parameters.keys())}")
        if not hasattr(CaroLogic, 'record_losing_moves'): raise AttributeError("Logic thiếu 'record_losing_moves'")
        sig_rec_loss = inspect.signature(CaroLogic.record_losing_moves); req_rec_loss = {'self','losing_state_move_pairs'};
        if not req_rec_loss.issubset(set(sig_rec_loss.parameters.keys())): raise AttributeError(f"Logic.record_losing_moves thiếu: {req_rec_loss-set(sig_rec_loss.parameters.keys())}")
        if not hasattr(CaroLogic,'board_tuple_to_string_key'): raise AttributeError("Logic thiếu 'board_tuple_to_string_key'")
        if not hasattr(CaroLogic,'string_key_to_board_tuple'): raise AttributeError("Logic thiếu 'string_key_to_board_tuple'")
        print("Chữ ký hàm CaroLogic (AutoSave V4) hợp lệ.")
    except AttributeError as e: messagebox.showerror("Lỗi Logic Signature", f"Lỗi file caro_logic.py:\n{e}"); exit()
    except Exception as e: messagebox.showwarning("Cảnh báo Logic", f"Kiểm tra logic lỗi:\n{e}");

    # Chạy App
    try: app = CaroApp(); app.mainloop()
    except Exception as e: print("LỖI CHẠY APP:"); traceback.print_exc(); messagebox.showerror("Lỗi nghiêm trọng", f"Lỗi khi chạy:\n{e}")

# --- END OF FILE caro.py (Learn Win/Loss - Always Record New Data - AutoSave - V5) ---