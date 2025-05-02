# Caro game training - chơi cờ caro

**Đây là game chơi cờ caro đơn giản, có hỗ trợ training để chương trình chơi game nhanh và thông minh hơn.**

* Mặc định chương trình chơi trên bàn cờ 25\*25
* Thời gian tối đa cài đặt hiện tại là 20 giây
* Kết thúc 1 ván auto lưu lại dữ liệu data vào file
* Sử dụng data để máy học đánh nhanh hơn


**Chương trình gồm 3 file chính:**

* Caro.py - Bàn cờ caro
* Caro\_logic.py - thuật toán xử lý, tính toán nước đi
* Train.py - phần mềm hỗ trợ training các nước đi
* File data json sẽ có dạng data-xx.json trong đó xx là kích cỡ bàn cờ (xx\*xx)

## *Thuật toán để tính toán nước đi.*


**Luồng Tính Toán Nước Đi Chính (find\_best\_move)** <br>
Hàm find\_best\_move hoạt động theo một hệ thống ưu tiên rõ ràng để quyết định nước đi:

1. **Khởi tạo và Chuẩn bị:**
    * **Sao chép bàn cờ:** Tạo một bản sao (current\_board) của bàn cờ hiện tại để không làm thay đổi trạng thái gốc trong quá trình tính toán.
    * **Chuyển đổi trạng thái:** Chuyển current\_board thành dạng tuple (board\_tuple) để có thể dùng làm key tra cứu trong các dictionary dữ liệu đã học.
    * **Xác định việc sử dụng data:** Quyết định có nên sử dụng dữ liệu đã học (ai\_winning\_moves, losing\_moves\_data) hay không, dựa trên cài đặt (use\_training\_data) và tham số force\_explore.
    * **Lấy ô trống tiềm năng:** Gọi get\_relevant\_empty\_cells (thường với distance=1 hoặc 2) để lấy danh sách các ô trống (possible\_moves) nằm gần các quân cờ đã đánh. Việc này giúp giới hạn không gian tìm kiếm, tăng hiệu suất đáng kể so với việc duyệt toàn bộ bàn cờ. Nếu không tìm thấy ô nào gần, nó sẽ mở rộng khoảng cách hoặc lấy tất cả ô trống còn lại.
    * **Lấy nước đi thua đã biết:** Tra cứu losing\_moves\_data bằng board\_tuple để lấy set các nước đi (known\_losing\_moves) mà AI đã từng đi ở trạng thái này và dẫn đến thua cuộc trong các ván trước.
2. **Ưu tiên 1: Thắng Ngay Lập Tức (WIN)**
    * Hàm lặp qua các possible\_moves.
    * Với mỗi ô trống tiềm năng (r, c):
        * **Giả lập:** Đặt quân O vào ô (r, c) trên bàn cờ tạm (temp\_board\_check).
        * **Kiểm tra thắng:** Gọi self.check\_win(temp\_board\_check, PLAYER\_O).
        * **Nếu thắng:** Nước đi (r, c) là nước thắng ngay lập tức. Hàm trả về ((r, c), "WIN") và kết thúc ngay lập tức. Đây là ưu tiên cao nhất.
        * **Hoàn tác:** Nếu không thắng, đặt lại ô (r, c) về EMPTY.
3. **Ưu tiên 2: Chặn Đối Thủ Thắng Ngay Lập Tức (BLOCK\_WIN)**
    * Nếu không tìm thấy nước thắng ngay, hàm tiếp tục lặp qua các possible\_moves (trong cùng vòng lặp với Ưu tiên 1).
    * Với mỗi ô trống tiềm năng (r, c):
        * **Giả lập:** Đặt quân X (đối thủ) vào ô (r, c) trên bàn cờ tạm.
        * **Kiểm tra đối thủ thắng:** Gọi self.check\_win(temp\_board\_check, PLAYER\_X).
        * **Nếu đối thủ thắng:** Điều này có nghĩa là nếu AI không đi vào ô (r, c) này, đối thủ sẽ đi vào đó và thắng. Do đó, AI bắt buộc phải đi vào ô (r, c) để chặn.
        * Hàm lưu lại nước đi chặn đầu tiên tìm thấy (block\_move) nhưng **không** kết thúc ngay (có thể có nhiều cách chặn, nhưng chặn đầu tiên là đủ).
        * **Hoàn tác:** Đặt lại ô (r, c) về EMPTY.
    * **Sau vòng lặp:** Nếu block\_move đã được tìm thấy (và không có win\_move), hàm trả về (block\_move, "BLOCK\_WIN"). Đây là ưu tiên cao thứ hai.
4. **Ưu tiên 3-5: Đánh giá Điểm và Chọn Nước Tốt Nhất (Dựa trên Heuristic)**
    * Nếu không có nước thắng hay chặn thắng ngay lập tức, AI cần đánh giá các nước đi tiềm năng khác.
    * **Lọc nước đi thua:** Tạo danh sách moves\_to\_evaluate bằng cách loại bỏ các nước đi trong known\_losing\_moves ra khỏi possible\_moves.
    * **Trường hợp đặc biệt:** Nếu sau khi lọc, moves\_to\_evaluate bị rỗng (nghĩa là tất cả các nước đi gần quân cờ đều đã từng dẫn đến thua), AI sẽ buộc phải đánh giá lại tất cả các nước trong possible\_moves (kể cả những nước đã thua) để chọn ra nước "đỡ tệ" nhất.
    * **Đánh giá từng nước đi:** Lặp qua các nước đi trong moves\_to\_evaluate:
        * Gọi self.evaluate\_move(current\_board, r, c, PLAYER\_O) cho từng nước đi (r, c).
        * **evaluate\_move hoạt động như sau:**
            * **Tính Điểm Tấn Công:** Giả lập đặt quân O vào ô (r, c). Gọi \_analyze\_patterns\_at và \_count\_lines\_with\_pattern để tìm các mẫu tấn công (4 hở, 3 hở, đôi 3,...) mà nước đi này tạo ra. Gán điểm số tương ứng (SCORE\_CREATE\_...) cho mẫu mạnh nhất.
            * **Tính Điểm Phòng Thủ:** Giả lập đặt quân X vào ô (r, c). Kiểm tra xem X có thắng ngay không (điểm SCORE\_BLOCK\_WIN rất cao). Nếu không, gọi \_analyze\_patterns\_at và \_count\_lines\_with\_pattern để tìm các mẫu nguy hiểm mà X tạo ra nếu họ đi vào đó. Gán điểm số chặn tương ứng (SCORE\_BLOCK\_...) cho mối nguy hiểm lớn nhất cần chặn.
            * **Kết hợp điểm:** Điểm cuối cùng của nước đi là điểm cao nhất trong số điểm tấn công, điểm phòng thủ, và một điểm vị trí cơ bản (SCORE\_POSITIONAL). Điều này ngầm ưu tiên phòng thủ (vì điểm chặn thường cao hơn điểm tạo).
            * **Trả về:** evaluate\_move trả về (final\_score, source\_string) (ví dụ: (100000, "BLOCK\_OPEN\_3")).
        * **Lưu kết quả đánh giá:** Lưu điểm và nguồn gốc vào dictionary evals.
        * **Cập nhật nước tốt nhất:** So sánh final\_score vừa tính với best\_score\_overall hiện tại. Nếu cao hơn, cập nhật best\_move\_overall, best\_score\_overall, và best\_source\_overall.
5. **Ưu tiên 6: Tránh Nước Đi Đã Biết Là Thua / Ép Khám Phá (FORCED\_NOVEL, RANDOM\_AVOID\_LOSS)**
    * **Kiểm tra force\_explore:** Tham số này thường được dùng bởi find\_novel\_move để buộc tìm nước khác.
    * **Kiểm tra nước tốt nhất có phải là nước thua không:** Sau khi đánh giá, kiểm tra xem best\_move\_overall có nằm trong known\_losing\_moves không (avoid\_loss\_triggered). Điều này có thể xảy ra nếu tất cả các lựa chọn khác đều tệ hơn đáng kể.
    * **Gọi find\_novel\_move:** Nếu force\_explore là True hoặc avoid\_loss\_triggered là True:
        * Gọi self.find\_novel\_move(current\_board, PLAYER\_O).
        * **find\_novel\_move hoạt động như sau:**
            * Lấy danh sách các nước đi tiềm năng.
            * Lấy nước thắng đã ghi nhận (learned\_win\_move) và danh sách nước thua (losing\_moves\_set) cho trạng thái hiện tại.
            * Tìm một nước đi hợp lệ (is\_valid\_move) mà **KHÔNG** phải là learned\_win\_move **VÀ KHÔNG** nằm trong losing\_moves\_set.
            * Nếu tìm thấy, trả về nước đi đó với nguồn "FORCED\_NOVEL".
            * Nếu không tìm thấy nước "mới lạ" nào (có thể do mọi nước đều đã học/thua), nó sẽ gọi lại find\_best\_move với use\_training\_data=False và force\_explore=True để tìm một nước đi tốt nhất dựa rein tính toán thuần túy (không dựa vào data học).
            * Nó còn xử lý trường hợp hiếm gặp khi nước fallback này cũng là nước thua, bằng cách thử chọn ngẫu nhiên một nước không thua (RANDOM\_AVOID\_LOSS).
        * **Sử dụng kết quả find\_novel\_move:** Nếu find\_novel\_move trả về một nước đi khác với best\_move\_overall, thì nước đi "mới lạ" này sẽ được chọn và trả về.
6. **Ưu tiên 7: Cân nhắc Nước Thắng Đã Ghi Nhận (LEARNED)**
    * Bước này chỉ thực hiện nếu **KHÔNG** có force\_explore hoặc avoid\_loss\_triggered.
    * Kiểm tra xem có nên dùng data không (attempt\_use\_data).
    * Tra cứu self.ai\_winning\_moves bằng board\_tuple để lấy recorded\_win\_tuple (nước đi mà AI đã từng thắng trong quá khứ ở trạng thái này).
    * **Kiểm tra điều kiện:**
        * Nước đi ghi nhận có tồn tại và hợp lệ không?
        * Nước đi ghi nhận có nằm trong known\_losing\_moves không? (Nếu có thì bỏ qua).
        * Lấy điểm đã đánh giá của nước đi ghi nhận (rec\_eval) từ dictionary evals.
        * So sánh điểm rec\_score với best\_score\_overall (nước tốt nhất tính được):
            * Không dùng nếu nước tốt nhất tính được là một nước chặn quan trọng (>= SCORE\_BLOCK\_OPEN\_3) mà nước ghi nhận lại không đạt ngưỡng đó.
            * Dùng nếu điểm của nước ghi nhận đủ tốt (>= SCORE\_CREATE\_OPEN\_3) VÀ không quá tệ so với nước tốt nhất tính được (ví dụ: rec\_score >= best\_score\_overall \* 0.7).
    * **Nếu đủ điều kiện:** Nước đi recorded\_win\_tuple được chọn và hàm trả về (recorded\_win\_tuple, "LEARNED").
7. **Ưu tiên 8: Trả về Nước Tốt Nhất Tính Được (Heuristic)**
    * Nếu không có nước thắng/chặn ngay, không bị ép tìm nước mới, và không dùng nước thắng đã ghi nhận, thì AI sẽ chọn nước đi có điểm số cao nhất tìm được trong quá trình đánh giá (Ưu tiên 3-5).
    * Hàm xác định lại final\_source dựa trên best\_score\_overall để đảm bảo nguồn gốc chính xác nhất theo thang điểm.
    * Trả về (best\_move\_overall, final\_source).
8. **Ưu tiên 9: Fallback Cuối Cùng (DEFAULT\_FALLBACK, RANDOM\_LAST\_RESORT)**
    * Xảy ra khi không tìm thấy best\_move\_overall nào sau quá trình đánh giá (rất hiếm, thường chỉ khi moves\_to\_evaluate rỗng).
    * Cố gắng lấy lại danh sách ô trống với khoảng cách xa hơn (distance=3) hoặc tất cả ô trống.
    * Lọc bỏ các nước thua đã biết nếu có thể.
    * Sắp xếp các lựa chọn còn lại theo khoảng cách đến tâm bàn cờ.
    * Chọn nước gần tâm nhất và trả về với nguồn "DEFAULT\_FALLBACK" hoặc tương tự.
    * Nếu không còn nước nào cả (bàn đầy hoặc lỗi), trả về (None, "NO\_MOVE") hoặc (None, "ERROR\_NO\_MOVE\_FOUND").

**Tóm tắt Nguồn Gốc Nước Đi (Source):**

| Source String | Ý Nghĩa | Ưu tiên |
| ------------- | ------- | ------- |
| WIN | Nước đi thắng ngay lập tức. | 1 (Cao) |
| BLOCK\_WIN | Chặn đối thủ thắng ngay lập tức. | 2 |
| BLOCK\_OPEN\_4 | Chặn 4 hở của đối thủ. | 3 |
| CREATE\_OPEN\_4 | Tạo 4 hở cho mình. | 4 |
| BLOCK\_OPEN\_3 | Chặn 3 hở của đối thủ (rất quan trọng). | 5 |
| CREATE\_FORK\_OPEN3 | Tạo nước đôi từ 2 đường 3 hở. | 6 |
| BLOCK\_FORK | Chặn nước đôi của đối thủ. | 7 |
| ... (Các mẫu chặn/tạo khác) ... | Ưu tiên chặn các mẫu mạnh của đối thủ hơn tạo mẫu tương đương. | ... |
| LEARNED | Sử dụng nước đi đã ghi nhận là thắng trong quá khứ (đủ điều kiện). | \~8 |
| FORCED\_NOVEL | Bị ép tìm nước mới (do explore hoặc tránh thua). | \~9 |
| NOVEL\_CALC\_\* | Kết quả tính toán khi find\_novel\_move gọi lại find\_best\_move. | \~9 |
| RANDOM\_AVOID\_LOSS | Random khi fallback của novel cũng thua. | \~9 |
| HEURISTIC\_PATTERN / HEURISTIC\_POS | Dựa trên điểm đánh giá mẫu yếu hoặc vị trí. | 10 |
| DEFAULT\_FALLBACK | Nước đi dự phòng cuối cùng (gần tâm). | 11 |
| ULTRA\_FALLBACK\_RANDOM | Random khi mọi cách khác đều thất bại. | 12 |
| NO\_MOVE | Không còn nước đi hợp lệ (bàn đầy). | - |
| ERROR\_\* / FIND\_MOVE\_EXC | Lỗi xảy ra trong quá trình tính toán. | - |

Quá trình này kết hợp cả chiến thuật trực tiếp (thắng/chặn), đánh giá heuristic phức tạp, học hỏi từ kinh nghiệm (ghi nhận thắng/thua) và cơ chế tránh lặp lại sai lầm, tạo nên một AI có khả năng chơi khá tốt và tiến bộ qua thời gian.

**Trainning sẽ có các phần sau:**

* Chọn kích thước bàn cờ để chạy
* Chọn số ván để chạy
* Chọn số luồng xử lý
* Chọn epsilon 
* Chọn số nước có thể lặp lại trong data ( sau số nước đó bắt buộc phải đánh nước mới, không lặp )

#### *Demo hình ảnh:*


**Màn hình chính**
<br>
![image](https://raw.githubusercontent.com/junlangzi/Caro-game-training/refs/heads/main/demo/demo1.png)
<br>
**Màn hình training**

![image](https://raw.githubusercontent.com/junlangzi/Caro-game-training/refs/heads/main/demo/demo2.png)
