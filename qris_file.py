import threading, time, json, cv2, requests, datetime, io, os, openpyxl
from flask import Flask, jsonify, render_template, request, Response, send_file, redirect, url_for, session
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ================= Flask App =================
app = Flask(__name__)
app.secret_key = os.urandom(24)  # lebih aman
ESP32_UNLOCK_URL = "http://192.168.11.149/unlock"  # Ganti IP ESP32 kamu

# ================= Global Variables =================
transaction_status = {"status":"idle","uid":"","amount":0}
transaction_log = []
frame_for_web = None
lock = threading.Lock()

camera_running = False
camera_thread = None
cap = None

# ================= Utility =================
def load_log_from_file():
    if not os.path.exists("transaksi.log"):
        print("⚠️ File log belum ada")
        return
    with open("transaksi.log", "r") as f:
        lines = f.readlines()
        for line in reversed(lines[-20:]):
            try:
                parts = line.strip().split("|")
                if len(parts) == 3:
                    time_str = parts[0].strip()
                    uid = parts[1].split(":")[1].strip()
                    amount_str = parts[2].split(":")[1].strip().replace("Rp","").replace(",","")
                    amount = int(amount_str)
                    transaction_log.append({"time":time_str,"uid":uid,"amount":amount})
            except Exception as e:
                print("❌ Gagal parsing log:", e)

def log_transaction(uid, amount):
    entry = {"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "uid": uid, "amount": amount}
    with lock:
        transaction_log.insert(0, entry)
    try:
        with open("transaksi.log","a") as f:
            f.write(f"{entry['time']} | UID: {uid} | Amount: Rp{amount}\n")
        print("✅ Log disimpan:", entry)
    except Exception as e:
        print("❌ Gagal simpan log:", e)

def get_summary(logs):
    count = len(logs)
    total_amount = sum(l["amount"] for l in logs)
    return count, total_amount

def filter_logs_by_date(logs, mode="day", date_str=None):
    filtered = []
    for log in logs:
        try:
            log_time = datetime.datetime.strptime(log["time"],"%Y-%m-%d %H:%M:%S")
        except:
            continue
        if mode=="day" and date_str and log_time.strftime("%Y-%m-%d")==date_str:
            filtered.append(log)
        elif mode=="month" and date_str and log_time.strftime("%Y-%m")==date_str:
            filtered.append(log)
    return filtered

# ================= Kamera Worker =================
def camera_worker():
    global frame_for_web, cap, camera_running
    cap = cv2.VideoCapture(0)
    detector = cv2.QRCodeDetector()
    if not cap.isOpened():
        print("❌ Tidak bisa buka kamera")
        camera_running = False
        return
    try:
        while camera_running:
            success, img = cap.read()
            if not success:
                time.sleep(0.1)
                continue
            with lock:
                frame_for_web = img.copy()
            data, _, _ = detector.detectAndDecode(img)
            if data:
                try:
                    qr_data = json.loads(data)
                    uid = str(qr_data.get("uid","")).strip()
                    amount = int(qr_data.get("amount",0))
                    if uid and amount >= 10000:
                        with lock:
                            transaction_status.update({"status":"success","uid":uid,"amount":amount})
                        try:
                            requests.get(ESP32_UNLOCK_URL, timeout=5)
                            print(f"✅ Pintu dibuka UID {uid} - Rp{amount}")
                        except Exception as e:
                            print("❌ Gagal kontak ESP32:", e)
                        log_transaction(uid, amount)
                        time.sleep(5)
                        with lock:
                            transaction_status.update({"status":"idle","uid":"","amount":0})
                    else:
                        with lock:
                            transaction_status.update({"status":"failed","uid":uid,"amount":amount})
                        time.sleep(3)
                        with lock:
                            transaction_status.update({"status":"idle","uid":"","amount":0})
                except json.JSONDecodeError:
                    print("❌ Format QR tidak valid")
                except Exception as e:
                    print("❌ Terjadi error:", e)
            time.sleep(0.05)
    finally:
        if cap:
            cap.release()
            cap = None
            print("📴 Kamera dimatikan")

def start_camera():
    global camera_running, camera_thread
    if not camera_running:
        camera_running = True
        camera_thread = threading.Thread(target=camera_worker, daemon=True)
        camera_thread.start()
        print("🎥 Kamera dimulai")

def stop_camera():
    global camera_running
    camera_running = False
    print("🛑 Kamera dihentikan")

def gen_frames():
    global frame_for_web
    while True:
        with lock:
            if frame_for_web is None:
                continue
            ret, buffer = cv2.imencode('.jpg', frame_for_web)
        if ret:
            frame = buffer.tobytes()
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+frame+b'\r\n')
        time.sleep(0.05)

# ================= Routes =================
@app.route("/video_feed")
def video_feed():
    if "user" not in session:
        return redirect(url_for("login"))
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/status")
def status():
    with lock:
        return jsonify(transaction_status)

@app.route("/log")
def get_log():
    with lock:
        return jsonify(transaction_log)

@app.route("/log/filter")
def filter_log():
    mode = request.args.get("mode","day")
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error":"Parameter 'date' diperlukan"}),400
    with lock:
        filtered = filter_logs_by_date(transaction_log, mode, date_str)
        count, total_amount = get_summary(filtered)
    return jsonify({"logs":filtered,"jumlah_transaksi":count,"total_nominal":total_amount})

@app.route("/doorlog", methods=["POST"])
def door_log():
    data = request.json
    print("📥 Notifikasi dari ESP32:", data.get("message",""))
    return jsonify({"status":"received"}), 200

@app.route("/scan", methods=["POST"])
def scan_qr():
    data = request.json
    uid = str(data.get("uid","")).strip()
    try: amount = int(data.get("amount",0))
    except: amount = 0

    if uid and amount >= 10000:
        with lock:
            transaction_status.update({"status":"success","uid":uid,"amount":amount})
        try:
            requests.get(ESP32_UNLOCK_URL, timeout=5)
        except: pass
        log_transaction(uid, amount)
        threading.Timer(5, lambda: transaction_status.update({"status":"idle","uid":"","amount":0})).start()
        return jsonify({"status":"success"}),200
    else:
        with lock:
            transaction_status.update({"status":"failed","uid":uid,"amount":amount})
        threading.Timer(3, lambda: transaction_status.update({"status":"idle","uid":"","amount":0})).start()
        return jsonify({"status":"failed","reason":"Amount kurang dari 10000"}),400

@app.route("/download/pdf")
def download_pdf():
    mode = request.args.get("mode")
    date_str = request.args.get("date")
    with lock:
        logs_to_export = transaction_log if not (mode and date_str) else filter_logs_by_date(transaction_log, mode, date_str)
        count, total_amount = get_summary(logs_to_export)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    data = [["Waktu","UID","Amount"]]+[[l["time"],l["uid"],f"Rp{l['amount']:,}"] for l in logs_to_export]
    data.append(["","Jumlah Transaksi",count])
    data.append(["","Total Nominal",f"Rp{total_amount:,}"])
    table = Table(data,colWidths=[150,150,150])
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2980b9")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#ecf0f1"))
    ]))
    doc.build([Paragraph("Log Transaksi",styles["Title"]),table])
    buffer.seek(0)
    filename = f"log_transaksi_{mode}_{date_str}.pdf" if mode and date_str else "log_transaksi.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/download/excel")
def download_excel():
    mode = request.args.get("mode")
    date_str = request.args.get("date")
    with lock:
        logs_to_export = transaction_log if not (mode and date_str) else filter_logs_by_date(transaction_log, mode, date_str)
        count, total_amount = get_summary(logs_to_export)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title="Log Transaksi"
    ws.append(["Waktu","UID","Amount"])
    for l in logs_to_export: ws.append([l["time"],l["uid"],l["amount"]])
    ws.append([])
    ws.append(["","Jumlah Transaksi",count])
    ws.append(["","Total Nominal",total_amount])
    for col in ws.columns:
        max_len = max(len(str(c.value)) if c.value else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len+2
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"log_transaksi_{mode}_{date_str}.xlsx" if mode and date_str else "log_transaksi.xlsx"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ================= Auth Routes =================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username=="admin" and password=="1234":
            session["user"]=username
            start_camera()
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Username/password salah")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user",None)
    stop_camera()
    return redirect(url_for("login"))

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    with lock:
        status_copy = transaction_status.copy()
        logs_copy = transaction_log.copy()
    return render_template("index2.html", status=status_copy, logs=logs_copy)

# ================= Main =================
if __name__=="__main__":
    load_log_from_file()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
