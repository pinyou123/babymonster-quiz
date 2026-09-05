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

        /* 💡 調整為彈性寬度 90%，留出防裁切邊距 */
        .container {
            width: 90%; max-width: 420px;
            background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 42, 117, 0.5); border-radius: 20px;
            padding: 25px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6); z-index: 1;
            margin: auto;
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
        
        /* 💡 右上角音樂按鈕容器組 */
        .music-controls {
            position: fixed;
            top: 15px;
            right: 15px;
            display: flex;
            gap: 6px;
            z-index: 999;
        }
        .music-btn, .music-select {
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid #ff2a75;
            color: #fff;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 0 10px rgba(255, 42, 117, 0.4);
            outline: none;
        }
        .music-select option {
            background: #0f172a;
            color: #fff;
        }

        /* 💡 遊戲說明按鈕樣式 */
        .btn-info {
            width: 100%;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 10px;
            color: #fff;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
        }

        /* 💡 遊戲說明彈窗遮罩與視窗 */
        .modal-overlay {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.75);
            display: flex; justify-content: center; align-items: center;
            z-index: 1000; padding: 20px;
        }
        .modal-content {
            background: #0f172a;
            border: 1px solid #ff2a75;
            border-radius: 16px;
            padding: 20px;
            max-width: 380px;
            width: 100%;
            color: #fff;
            box-shadow: 0 0 20px rgba(255, 42, 117, 0.5);
        }
        .rules-body p {
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 10px;
            color: #cbd5e1;
        }

        /* 📱 手機版專屬響應式規則（螢幕小於 768px 自動生效） */
        @media (max-width: 768px) {
            body { padding: 10px; }
            .bg-grid { grid-template-columns: 1fr; grid-template-rows: repeat(4, 1fr); }
            .container { width: 95%; padding: 18px 14px; }
            .music-controls { top: 10px; right: 10px; }
            .music-btn, .music-select { padding: 6px 10px; font-size: 12px; }
        }
    </style>
</head>
<body>
    <audio id="lobby-bgm" loop preload="auto">
        <source id="bgm-source" src="{{ url_for('static', filename='bgm.mp3') }}" type="audio/mpeg">
    </audio>

    <!-- 右上角音樂控制區：選單 + 開關按鈕 -->
    <div class="music-controls">
        <select id="bgm-select" class="music-select" onchange="selectTrack(this.value)">
            <option value="{{ url_for('static', filename='bgm.mp3') }}">🎵 I LIKE IT</option>
            <option value="{{ url_for('static', filename='bgm2.mp3') }}">🎵 LIKE THAT</option>
            <option value="{{ url_for('static', filename='bgm3.mp3') }}">🎵 DRIP</option>
            <option value="{{ url_for('static', filename='bgm4.mp3') }}">🎵 FOREVER</option>
            <option value="{{ url_for('static', filename='bgm5.mp3') }}">🎵 REALLY LIKE YOU</option>
            <option value="{{ url_for('static', filename='bgm6.mp3') }}">🎵 SUPA DUPA LUV</option>
            <option value="{{ url_for('static', filename='bgm7.mp3') }}">🎵 LOVE IN MY HEART</option>
        </select>
        <button id="bgm-toggle-btn" class="music-btn" onclick="toggleMusic(event)">🎵 音樂: ON</button>
    </div>
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
            <button class="btn-info" onclick="openRulesModal()">📖 遊戲說明</button>
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
    
    <!-- 💡 請把遊戲說明彈窗 Modal 直接塞在這裡（.container 外面、<script> 上面） -->
    <div id="rules-modal" class="modal-overlay hidden">
        <div class="modal-content">
            <h2 style="color:#ff2a75; margin-bottom:15px; text-align:center;">📜 遊戲規則說明</h2>
            <div class="rules-body">
                <p><b>1. 答題時間：</b>每題有 10 秒倒數時間（影片題會先播放完畢才開始倒數）。</p>
                <p><b>2. 計分方式：</b>答對獲得題目基礎分 + 剩餘時間加分；答錯不倒扣。</p>
                <p><b>3. 題型種類：</b>包含文字題、圖片題以及影片題，考驗你對 BABYMONSTER 的熟悉度！</p>
                <p><b>4. 防刷機制：</b>遊戲中途重載將繼續回答當前題目，且不顯示正確答案選項。</p>
            </div>
            <button class="btn-submit" onclick="closeRulesModal()" style="margin-top:15px;">返回主頁</button>
        </div>
    </div>

   <script>
    const socket = io();
    let myName = "";
    let myRoom = "";
    let timerInterval = null;
    let timeLeft = 10;
    let hasAnswered = false;
    let isMusicPlaying = true;

    // 💡 1. 遊戲說明彈窗開關函式
    function openRulesModal() {
        document.getElementById('rules-modal').classList.remove('hidden');
    }

    function closeRulesModal() {
        document.getElementById('rules-modal').classList.add('hidden');
    }

    // 💡 2. 下拉選單切換歌曲邏輯
    function selectTrack(srcUrl) {
        const bgm = document.getElementById('lobby-bgm');
        const btn = document.getElementById('bgm-toggle-btn');
        if (!bgm) return;

        bgm.src = srcUrl;

        if (isMusicPlaying) {
            bgm.volume = 0.4;
            bgm.play().then(() => {
                if (btn) btn.innerText = "🎵 音樂: ON";
            }).catch(err => console.log("音樂播放受限:", err));
        }
    }

    // 💡 3. 自動播放核心監聽
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

    // 💡 1. 頁面載入時檢查紀錄
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

    // 💡 2. 玩家加入遊戲
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

    // 💡 3. 接收專屬房間號，並紀錄 myRoom
    socket.on('room_assigned', (data) => {
        myRoom = data.room; // 確保有拿到房間號
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
    
    // 💡 補上遺漏的 startGame 函式（發送開始遊戲訊號）
    function startGame() {
        if (!myRoom && myName) myRoom = "user_" + myName;
        socket.emit('start_game', { room: myRoom });
    }

    // 💡 4. 接收新題目（防刷新關鍵：如果 myRoom 是空的，自動從暱稱重新綁定）
    socket.on('new_question', (data) => {
        // 1. 強制確保 myRoom 有值
        if (!myRoom && myName) myRoom = "user_" + myName;

        // 2. 核心修復：強制隱藏登入與大廳畫面，開啟遊戲視窗
        document.getElementById('setup-view').classList.add('hidden');
        document.getElementById('lobby-view').classList.add('hidden');
        document.getElementById('game-view').classList.remove('hidden');

        hasAnswered = false;
        clearInterval(timerInterval);

        let q = data.question;
        let scoreText = q.base_score ? ` (${q.base_score}分)` : '';
        
        let html = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#ff2a75; font-weight:bold;">第 ${data.index + 1} / ${data.total} 題${scoreText}</span>
                <span id="timer-text" style="color:#fff; font-weight:bold;">⏱️ 10 秒</span>
            </div>
            <div class="timer-container"><div id="timer-bar" class="timer-bar"></div></div>
        `;

        if (q.image_url) {
            html += `<img src="${q.image_url}" class="quiz-image" style="width:100%; max-height:180px; object-fit:cover; border-radius:10px; margin-bottom:12px;" alt="題目圖片">`;
        }

        if (q.video_url) {
            html += `
                <video id="quiz-video" src="${q.video_url}" autoplay muted playsinline 
                       style="width:100%; max-height:200px; border-radius:10px; margin-bottom:12px; object-fit:cover;">
                </video>
            `;
        }

        html += `<p style="font-size:15px; font-weight:bold; margin-bottom:15px; color:#fff;">${q.question}</p>`;
        html += `<div id="options-box">`;

        if (q.options) {
            q.options.forEach(opt => {
                html += `<button class="quiz-option" onclick="clickAnswer(this, '${opt}', '${q.answer}')">${opt}</button>`;
            });
        }
        html += `</div>`;

        document.getElementById('quiz-box').innerHTML = html;

        const videoEl = document.getElementById('quiz-video');
        if (videoEl) {
            const allBtns = document.querySelectorAll('.quiz-option');
            allBtns.forEach(b => b.disabled = true);
            
            document.getElementById('timer-text').innerText = "🎥 觀看影片中...";

            videoEl.onended = () => {
                allBtns.forEach(b => b.disabled = false);
                startTimer(q.answer);
            };

            videoEl.onerror = () => {
                allBtns.forEach(b => b.disabled = false);
                startTimer(q.answer);
            };
        } else {
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

    // 💡 點擊選項（不顯示真正的正確答案，防刷題）
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

    // 💡 超時未答（不顯示正確答案）
    function timeOutAnswer(correct) {
        hasAnswered = true;
        const allBtns = document.querySelectorAll('.quiz-option');
        allBtns.forEach(b => {
            b.disabled = true;
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

    // 💡 5. 遊戲結束顯示最終分數
socket.on('game_over', (data) => {
    sessionStorage.removeItem('quiz_username');
    sessionStorage.removeItem('quiz_bias');
    clearInterval(timerInterval);
    
    let html = `<h2 style="color:#ff2a75; text-align:center; margin-bottom:15px;">🏆 最終分數</h2>`;
    data.leaderboard.forEach((p) => {
        html += `<div class="roster-item">
            玩家: <b>${p.name}</b> (${p.bias}) <br>
            總得分: <span style="color:#ff2a75; font-weight:bold; font-size:16px;">${p.score}</span> 分
        </div>`;
    });

    // 💡 1. 將 location.reload() 改為 restartGame()
    html += `<button class="btn-submit" onclick="restartGame()" style="margin-top:20px;">🔄 再次挑戰</button>`;
    document.getElementById('quiz-box').innerHTML = html;
});

// 新增這個函式，徹底清空快取再刷頁面
function restartGame() {
    sessionStorage.clear();
    location.reload();
}
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('join_room')
def handle_join(data):
    name = data.get('name', '').strip()
    bias = data.get('bias', 'Ruka')
    
    # 💡 核心修改：使用「暱稱」當作房間 ID（防刷新關閉）
    room = f"user_{name}"
    join_room(room)

    # 1. 建立或重置房間（當房間不存在或上局已結束時）
    if room not in ROOMS or ROOMS[room].get("status") == "FINISHED":
        ROOMS[room] = {
            "players": [],
            "status": "LOBBY",
            "selected_questions": [],
            "current_q": 0
        }

    r = ROOMS[room]

    # 2. 檢查玩家資料
    player = next((p for p in r['players'] if p['name'] == name), None)
    if not player:
        r['players'].append({"name": name, "bias": bias, "score": 0})
    else:
        player['bias'] = bias

    # 💡 3. 防刷新：如果遊戲正在進行中，帶回當前題目
    if r['status'] == "PLAYING":
        q_idx = r['current_q']
        if q_idx < len(r['selected_questions']):
            emit('new_question', {
                "question": r['selected_questions'][q_idx],
                "index": q_idx,
                "total": len(r['selected_questions'])
            }, room=room)
            return  # 成功留在遊戲內，不跳回大廳

    # 4. 未在遊戲中則正常回傳房間並顯示大廳
    emit('room_assigned', {"room": room, "players": r['players']}, room=room)

@socketio.on('start_game')
def handle_start(data):
    # 💡 1. 改用 .get() 避免前端沒傳 room 時 KeyErrer 報錯
    room = data.get('room')
    
    # 💡 2. 防呆修復：若 room 是空的或不在 ROOMS 中，自動搜尋對應的專屬房間
    if not room or room not in ROOMS:
        for r_id in ROOMS:
            room = r_id
            break

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
    room = data.get('room')
    name = data.get('name')
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