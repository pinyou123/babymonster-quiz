import sys
import random
import copy
from gevent import monkey

import uuid
from flask import request

if 'spyder_kernels' not in sys.modules:
    monkey.patch_all()

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit, join_room
from questions import QUESTION1, QUESTION2, QUESTION3, QUESTION_PICTURE, QUESTION_VIDEO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'babymonster_quiz_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")


ROOMS = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>BABYMONSTER 快問快答遊戲</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; }
        
        body {
            position: relative;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow-x: hidden;
            background-color: #0f172a;
        }

        .bg-grid {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; z-index: -2;
        }
        .bg-grid div { background-size: cover; background-position: center; }
        .bg-img1 { background-image: url('/static/babymo.jpg'); }
        .bg-img2 { background-image: url('/static/babymo2.jpg'); }
        .bg-img3 { background-image: url('/static/babymo3.jpg'); }
        .bg-img4 { background-image: url('/static/babymo4.webp'); }

        .bg-overlay {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(13, 15, 23, 0.55); z-index: -1;
        }

        .container {
            width: 100%; max-width: 420px;
            background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 42, 117, 0.5); border-radius: 20px;
            padding: 25px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6); z-index: 1;
        }

        .title {
            text-align: center; font-size: 24px; font-weight: 900;
            color: #ff2a75; text-shadow: 0 0 15px rgba(255, 42, 117, 0.9); margin-bottom: 20px;
        }

        .form-group { margin-bottom: 16px; }
        label { display: block; font-size: 14px; color: #ffffff; font-weight: bold; margin-bottom: 6px; }
        input {
            width: 100%; padding: 11px 14px; border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.3); background: rgba(15, 23, 42, 0.6);
            color: #fff; font-size: 14px; outline: none;
        }

        .bias-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
        .bias-option input[type="radio"] { display: none; }
        .bias-card {
            display: block; text-align: center; padding: 9px 4px;
            background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: bold; color: #f1f5f9;
        }
        .bias-option input[type="radio"]:checked + .bias-card {
            background: #ff2a75; color: #fff; border-color: #ff2a75; box-shadow: 0 0 12px rgba(255, 42, 117, 0.9);
        }

        .btn-submit {
            width: 100%; padding: 13px; background: linear-gradient(135deg, #ff2a75, #ff758c);
            border: none; border-radius: 10px; color: #fff; font-size: 16px; font-weight: bold;
            cursor: pointer; margin-top: 10px; box-shadow: 0 4px 15px rgba(255, 42, 117, 0.5);
        }

        .hidden { display: none; }

        .roster-item {
            background: rgba(15, 23, 42, 0.75); color: #ffffff; padding: 10px 14px;
            margin-top: 8px; border-radius: 8px; border-left: 4px solid #ff2a75; font-size: 14px;
        }

        /* 答題選項與反饋 */
        .quiz-option {
            width: 100%; padding: 12px; margin-top: 10px;
            background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px; color: #fff; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.2s;
        }
        .quiz-option.correct { background: #10b981 !important; border-color: #10b981 !important; color: #fff; }
        .quiz-option.wrong { background: #ef4444 !important; border-color: #ef4444 !important; color: #fff; }

        /* 倒數計時條 */
        .timer-container {
            width: 100%; height: 8px; background: rgba(255, 255, 255, 0.2);
            border-radius: 4px; margin: 15px 0; overflow: hidden;
        }
        .timer-bar {
            height: 100%; width: 100%; background: #ff2a75; transition: width 0.1s linear;
        }
        
        .music-btn {
            position: fixed;
            top: 15px;
            right: 15px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid #ff2a75;
            color: #fff;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: bold;
            cursor: pointer;
            z-index: 999;
            box-shadow: 0 0 10px rgba(255, 42, 117, 0.4);
        }
    </style>
</head>
<body>
    <audio id="lobby-bgm" loop preload="auto">
        <source src="{{ url_for('static', filename='bgm.mp3') }}" type="audio/mpeg">
    </audio>

    <!-- 右上角音樂按鈕 -->
    <button id="bgm-toggle-btn" class="music-btn" onclick="toggleMusic(event)">🎵 音樂: ON</button>
    <div class="bg-grid">
        <div class="bg-img1"></div><div class="bg-img2"></div>
        <div class="bg-img3"></div><div class="bg-img4"></div>
    </div>
    <div class="bg-overlay"></div>

    <div class="container">
        <h1 class="title">🎀 BABYMONSTER<br>快問快答遊戲</h1>

        <!-- 1. 個人資料填寫 -->
        <div id="setup-view">
            <div class="form-group">
                <label>你的暱稱</label>
                <input type="text" id="username" placeholder="請輸入暱稱">
            </div>

            <div class="form-group">
                <label>你擔誰（本命成員）</label>
                <div class="bias-grid">
                    <label class="bias-option"><input type="radio" name="bias" value="Ruka" checked><span class="bias-card">Ruka</span></label>
                    <label class="bias-option"><input type="radio" name="bias" value="Pharita"><span class="bias-card">Pharita</span></label>
                    <label class="bias-option"><input type="radio" name="bias" value="Asa"><span class="bias-card">Asa</span></label>
                    <label class="bias-option"><input type="radio" name="bias" value="Ahyeon"><span class="bias-card">Ahyeon</span></label>
                    <label class="bias-option"><input type="radio" name="bias" value="Rami"><span class="bias-card">Rami</span></label>
                    <label class="bias-option"><input type="radio" name="bias" value="Rora"><span class="bias-card">Rora</span></label>
                    <label class="bias-option" style="grid-column: span 3;"><input type="radio" name="bias" value="Chiquita"><span class="bias-card">Chiquita</span></label>
                </div>
            </div>

            <button class="btn-submit" onclick="joinGame()">🎮 準備進入大廳</button>
        </div>

        <!-- 2. 大廳視窗 -->
        <div id="lobby-view" class="hidden">
            <h2 style="color:#ff2a75; font-size:18px; text-align:center;">🏠 準備中</h2>
            <div id="player-list" style="margin: 15px 0;"></div>
            <button class="btn-submit" onclick="startGame()">🚀 開始挑戰 </button>
        </div>

        <!-- 3. 答題視窗 -->
        <div id="game-view" class="hidden">
            <div id="quiz-box"></div>
        </div>
    </div>

   <script>
        const socket = io();
        let myName = "";
        let myRoom = ""; // 💡 儲存後端發配的個人專屬獨立房間 ID
        let timerInterval = null;
        let timeLeft = 10;
        let hasAnswered = false;
        let isMusicPlaying = true;

        // 💡 自動播放核心監聽
        function initAutoplay() {
            const startMusicOnFirstClick = () => {
                const bgm = document.getElementById('lobby-bgm');
                if (bgm && isMusicPlaying && bgm.paused) {
                    bgm.volume = 0.4;
                    bgm.play().then(() => {
                        console.log("自動播放成功！");
                    }).catch(err => console.log("自動播放等待互動:", err));
                }
                document.removeEventListener('click', startMusicOnFirstClick);
                document.removeEventListener('keydown', startMusicOnFirstClick);
            };

            document.addEventListener('click', startMusicOnFirstClick);
            document.addEventListener('keydown', startMusicOnFirstClick);
        }

        // 💡 1. 頁面載入時檢查是否有未完成的遊戲紀錄（重連機制）
window.addEventListener('DOMContentLoaded', () => {
    initAutoplay();
    
    const savedName = sessionStorage.getItem('quiz_username');
    const savedBias = sessionStorage.getItem('quiz_bias');
    if (savedName) {
        document.getElementById('username').value = savedName;
        myName = savedName;
        if (savedBias) {
            const biasRadio = document.querySelector(`input[name="bias"][value="${savedBias}"]`);
            if (biasRadio) biasRadio.checked = true;
        }
        socket.emit('join_room', { name: savedName, bias: savedBias || 'Ruka' });
    }
});

function toggleMusic(e) {
    if (e) e.stopPropagation();
    const bgm = document.getElementById('lobby-bgm');
    const btn = document.getElementById('bgm-toggle-btn');
    if (!bgm) return;

    if (bgm.paused) {
        bgm.volume = 0.4;
        bgm.play().then(() => {
            isMusicPlaying = true;
            if (btn) btn.innerText = "🎵 音樂: ON";
        });
    } else {
        bgm.pause();
        isMusicPlaying = false;
        if (btn) btn.innerText = "🔇 音樂: OFF";
    }
}

// 💡 2. 玩家登入並儲存資料到 Session
function joinGame() {
    myName = document.getElementById('username').value.trim();
    const biasEl = document.querySelector('input[name="bias"]:checked');
    const bias = biasEl ? biasEl.value : 'Ruka';

    if (!myName) return alert("請輸入暱稱！");

    sessionStorage.setItem('quiz_username', myName);
    sessionStorage.setItem('quiz_bias', bias);

    const bgm = document.getElementById('lobby-bgm');
    if (bgm && isMusicPlaying && bgm.paused) {
        bgm.volume = 0.4;
        bgm.play().catch(err => console.log("音樂播放受限:", err));
    }

    socket.emit('join_room', { name: myName, bias: bias });
}

// 💡 3. 核心修復：接收專屬房間號，並將畫面切換至大廳（解決卡住問題）
socket.on('room_assigned', (data) => {
    myRoom = data.room; // 保存後端發配的個人獨立房間號
    document.getElementById('setup-view').classList.add('hidden');
    document.getElementById('lobby-view').classList.remove('hidden');

    let html = "<h4 style='color:#ffffff; margin-bottom:10px; font-size:14px;'>大廳玩家:</h4>";
    data.players.forEach(p => { 
        html += `<div class="roster-item">
            👤 <b>${p.name}</b> - <span style="color:#cbd5e1;">本命:</span> <span style="color:#ff758c; font-weight:bold;">${p.bias}</span>
        </div>`; 
    });
    document.getElementById('player-list').innerHTML = html;
});

        // 💡 接收後端發配的個人獨立房間，並渲染個人大廳
        socket.on('room_assigned', (data) => {
            myRoom = data.room;
            document.getElementById('setup-view').classList.add('hidden');
            document.getElementById('lobby-view').classList.remove('hidden');

            let html = "<h4 style='color:#ffffff; margin-bottom:10px; font-size:14px;'>大廳玩家:</h4>";
            data.players.forEach(p => { 
                html += `<div class="roster-item">
                    👤 <b>${p.name}</b> - <span style="color:#cbd5e1;">本命:</span> <span style="color:#ff758c; font-weight:bold;">${p.bias}</span>
                </div>`; 
            });
            document.getElementById('player-list').innerHTML = html;
        });

        function startGame() {
            socket.emit('start_game', { room: myRoom });
        }

        // 接收新題目
        socket.on('new_question', (data) => {
            document.getElementById('setup-view').classList.add('hidden');
            document.getElementById('lobby-view').classList.add('hidden');
            document.getElementById('game-view').classList.remove('hidden');

            hasAnswered = false;
            clearInterval(timerInterval);

            let q = data.question;
            let scoreText = q.score ? ` (${q.score}分)` : '';
            
            let html = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#ff2a75; font-weight:bold;">第 ${data.index + 1} / ${data.total} 題${scoreText}</span>
                    <span id="timer-text" style="color:#fff; font-weight:bold;">⏱️ 10 秒</span>
                </div>
                <div class="timer-container"><div id="timer-bar" class="timer-bar"></div></div>
            `;

            // 1. 圖片題渲染
            if (q.image_url) {
                html += `<img src="${q.image_url}" class="quiz-image" style="width:100%; max-height:180px; object-fit:cover; border-radius:10px; margin-bottom:12px;" alt="題目圖片">`;
            }

            // 2. 影片題渲染（強制靜音）
            if (q.video_url) {
                html += `
                    <video id="quiz-video" src="${q.video_url}" autoplay muted playsinline 
                           style="width:100%; max-height:200px; border-radius:10px; margin-bottom:12px; object-fit:cover;">
                    </video>
                `;
            }

            html += `<p style="font-size:15px; font-weight:bold; margin-bottom:15px; color:#fff;">${q.question}</p>`;
            html += `<div id="options-box">`;

            // 渲染選項
            if (q.options) {
                q.options.forEach(opt => {
                    html += `<button class="quiz-option" onclick="clickAnswer(this, '${opt}', '${q.answer}')">${opt}</button>`;
                });
            }
            html += `</div>`;

            document.getElementById('quiz-box').innerHTML = html;

            // 💡 判斷：如果是影片題，先禁用所有按鈕，等影片結束才解鎖並開始計時
            const videoEl = document.getElementById('quiz-video');
            if (videoEl) {
                // 1. 禁用所有選項按鈕
                const allBtns = document.querySelectorAll('.quiz-option');
                allBtns.forEach(b => b.disabled = true);
                
                document.getElementById('timer-text').innerText = "🎥 觀看影片中...";

                // 2. 影片播放結束時解鎖按鈕並開始倒數
                videoEl.onended = () => {
                    allBtns.forEach(b => b.disabled = false);
                    startTimer(q.answer);
                };

                // 防呆：若影片載入失敗，3 秒後強制解鎖並開跑
                videoEl.onerror = () => {
                    allBtns.forEach(b => b.disabled = false);
                    startTimer(q.answer);
                };
            } else {
                // 文字題與圖片題：直接開始倒數
                startTimer(q.answer);
            }
        });

        function startTimer(correctAnswer) {
            timeLeft = 10;
            const bar = document.getElementById('timer-bar');
            const text = document.getElementById('timer-text');

            timerInterval = setInterval(() => {
                timeLeft -= 0.1;
                if (timeLeft <= 0) {
                    timeLeft = 0;
                    clearInterval(timerInterval);
                    if (!hasAnswered) {
                        timeOutAnswer(correctAnswer);
                    }
                }
                text.innerText = `⏱️ ${Math.ceil(timeLeft)} 秒`;
                bar.style.width = `${(timeLeft / 10) * 100}%`;
            }, 100);
        }

        function clickAnswer(btn, selected, correct) {
            if (hasAnswered) return;
            hasAnswered = true;
            clearInterval(timerInterval);

            const allBtns = document.querySelectorAll('.quiz-option');
            allBtns.forEach(b => b.disabled = true);

            const isCorrect = (selected === correct);

            if (isCorrect) {
                btn.classList.add('correct');
            } else {
                btn.classList.add('wrong');
                allBtns.forEach(b => {
                    if (b.innerText === correct) b.classList.add('correct');
                });
            }

            setTimeout(() => {
                socket.emit('submit_answer', {
                    room: myRoom,
                    name: myName,
                    is_correct: isCorrect,
                    time_left: timeLeft
                });
            }, 1200);
        }

        function timeOutAnswer(correct) {
            hasAnswered = true;
            const allBtns = document.querySelectorAll('.quiz-option');
            allBtns.forEach(b => {
                b.disabled = true;
                if (b.innerText === correct) b.classList.add('correct');
            });

            setTimeout(() => {
                socket.emit('submit_answer', {
                    room: myRoom,
                    name: myName,
                    is_correct: false,
                    time_left: 0
                });
            }, 1200);
        }

        // 💡 3. 遊戲結束時清除紀錄
socket.on('game_over', (data) => {
    sessionStorage.removeItem('quiz_username');
    sessionStorage.removeItem('quiz_bias');
    clearInterval(timerInterval);
    
    // 1. 將標題改為「最終分數」
    let html = `<h2 style="color:#ff2a75; text-align:center; margin-bottom:15px;">🏆 最終分數</h2>`;
    
    // 2. 移除「第 X 名」，僅顯示玩家暱稱、本命與總得分
    data.leaderboard.forEach((p) => {
        html += `<div class="roster-item">
            玩家: <b>${p.name}</b> (${p.bias}) <br>
            總得分: <span style="color:#ff2a75; font-weight:bold; font-size:16px;">${p.score}</span> 分
        </div>`;
    });

    html += `<button class="btn-submit" onclick="location.reload()" style="margin-top:20px;">🔄 再次挑戰</button>`;
    document.getElementById('quiz-box').innerHTML = html;
});
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('join_room')
def handle_join(data):
    # 💡 使用玩家當前的 Socket 連線 ID 作為個人專屬房間，實現完全獨立遊玩
    room = request.sid
    name = data['name']
    bias = data['bias']
    join_room(room)

    # 1. 建立或重置房間（當上局已結束時）
    if room not in ROOMS or ROOMS[room].get("status") == "FINISHED":
        ROOMS[room] = {
            "players": [],
            "status": "LOBBY",
            "selected_questions": [],
            "current_q": 0
        }

    r = ROOMS[room]

    # 2. 檢查玩家是否已經存在（更新本命，不重複新增）
    player = next((p for p in r['players'] if p['name'] == name), None)
    if not player:
        r['players'].append({"name": name, "bias": bias, "score": 0})
    else:
        player['bias'] = bias  # 若重複連線，僅更新本命資料

    # 3. 核心：如果遊戲進行中，直接把玩家拉回當前的題目（防刷新刷分）
    if r['status'] == "PLAYING":
        q_idx = r['current_q']
        if q_idx < len(r['selected_questions']):
            emit('new_question', {
                "question": r['selected_questions'][q_idx],
                "index": q_idx,
                "total": len(r['selected_questions'])
            })
            return  # 結束流程，不更新大廳列表

    # 4. 回傳個人專屬房間 ID 給前端並更新個人大廳
    emit('room_assigned', {"room": room, "players": r['players']}, room=room)

@socketio.on('start_game')
def handle_start(data):
    room = data['room']
    if room in ROOMS:
        r = ROOMS[room]
        r['status'] = "PLAYING"
        r['current_q'] = 0
        
        # 重置玩家分數
        for p in r['players']:
            p['score'] = 0
            
        # 1. 從各類題庫隨機抽取指定數量（使用 min 避免題庫不足報錯）
        q1_sample = random.sample(QUESTION1, min(7, len(QUESTION1)))
        q2_sample = random.sample(QUESTION2, min(7, len(QUESTION2)))
        q3_sample = random.sample(QUESTION3, min(5, len(QUESTION3)))
        pic_sample = random.sample(QUESTION_PICTURE, min(7, len(QUESTION_PICTURE)))
        vid_sample = random.sample(QUESTION_VIDEO, min(4, len(QUESTION_VIDEO)))

        # 深拷貝題目，避免打亂選項時修改到全域變數
        selected_raw = copy.deepcopy(q1_sample + q2_sample + q3_sample + pic_sample + vid_sample)

        # 2. 為題目注入基礎分數權重 (Base Score)
        for q in selected_raw:
            if q in q1_sample:
                q['base_score'] = 100  # 簡單文字題
            elif q in q2_sample:
                q['base_score'] = 150  # 中等文字題
            elif q in q3_sample:
                q['base_score'] = 200  # 困難文字題
            else:
                q['base_score'] = 150  # 圖片 / 影片題

            # 3. 打亂該題的選項順序（正確答案 answer 保持不變）
            if 'options' in q and isinstance(q['options'], list):
                random.shuffle(q['options'])

        # 4. 合併並打亂題目出現順序
        random.shuffle(selected_raw)
        
        r['selected_questions'] = selected_raw
        send_question(room)

def send_question(room):
    r = ROOMS[room]
    q_idx = r['current_q']
    if q_idx < len(r['selected_questions']):
        emit('new_question', {
            "question": r['selected_questions'][q_idx],
            "index": q_idx,
            "total": len(r['selected_questions'])
        }, room=room)
    else:
        # 💡 遊戲結束時將狀態改為 FINISHED
        r['status'] = "FINISHED"
        leaderboard = sorted(r['players'], key=lambda x: x['score'], reverse=True)
        emit('game_over', {"leaderboard": leaderboard}, room=room)

@socketio.on('submit_answer')
def handle_answer(data):
    room = data['room']
    name = data['name']
    is_correct = data.get('is_correct', False)
    time_left = data.get('time_left', 0)
    
    if room in ROOMS:
        r = ROOMS[room]
        
        # 獲取當前題目的難度基礎分
        current_q = r['selected_questions'][r['current_q']]
        base_score = current_q.get('base_score', 100)
        
        if is_correct:
            # 保留原本計算方式：難度基礎分 + 時間加分 (剩餘秒數 * 10)
            earned_score = base_score + int(time_left * 10)
            for p in r['players']:
                if p['name'] == name:
                    p['score'] += earned_score

        # 推進至下一題
        r['current_q'] += 1
        send_question(room)

if __name__ == '__main__':
    print("🚀 BABYMONSTER 伺服器啟動中...")
    print("👉 請開啟網址: http://127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)