import sys
import random
import copy
import json
import os
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
GLOBAL_LEADERBOARD = []  # 儲存所有玩家的歷史紀錄
LEADERBOARD_FILE = "leaderboard.json"

# 💡 伺服器啟動時自動嘗試讀取舊有紀錄
if os.path.exists(LEADERBOARD_FILE):
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            GLOBAL_LEADERBOARD = json.load(f)
            print(f"✅ 成功載入 {len(GLOBAL_LEADERBOARD)} 筆歷史排行榜紀錄！")
    except Exception as e:
        print(f"⚠️ 讀取排行榜檔案失敗: {e}")

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

        .hidden { display: none !important; }

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
        
        .developer-footer {
    margin-top: 20px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    text-align: center;
    font-size: 11px;
    color: #94a3b8;
}
.developer-footer a {
    color: #ff758c;
    text-decoration: none;
    font-weight: bold;
    margin: 0 4px;
    transition: color 0.2s;
}
.developer-footer a:hover {
    color: #ff2a75;
    text-decoration: underline;
}

.leaderboard-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    color: #fff;
    text-align: center;
}
.leaderboard-table th, .leaderboard-table td {
    padding: 8px 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.leaderboard-table th {
    color: #ff2a75;
    background: rgba(255, 42, 117, 0.1);
}
    </style>
</head>
<body>
    <audio id="lobby-bgm" loop preload="auto">
        <source id="bgm-source" src="{{ url_for('static', filename='bgm.mp3') }}" type="audio/mpeg">
    </audio>

    <!-- 右上角音樂控制區：彩蛋按鈕 + 選單 + 開關按鈕 -->
    <div class="music-controls">
        <button class="music-btn" onclick="openBangModal()">🎬 點一下看看</button>
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
            
            <!-- 💡 新增年齡輸入框 -->
            <div class="form-group">
                <label>你的年齡</label>
                <input type="number" id="user-age" placeholder="請輸入年齡" min="1" max="99">
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
            <button class="btn-info" onclick="openLeaderboardModal()" style="margin-top: 8px;">🏆 排行榜</button>
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
        
        <!-- 💡 請把開發者資訊貼在這裡 -->
        <div class="developer-footer">
            BABYMONSTER 官方：IG @babymonster_ygofficial / YT BABYMONSTER<br>
            開發者：<b>Pinyou Liu</b>（IG / Threads：@pinyou890201）
        </div>

    </div>
    
    <!-- 💡 確保有加上 hidden 類別，這樣預設就不會自動跳出來 -->
    <div id="rules-modal" class="modal-overlay hidden">
        <div class="modal-content">
            <h2 style="color:#ff2a75; margin-bottom:15px; text-align:center;">📜 遊戲規則說明</h2>
            <div class="rules-body">
                <p><b>1. 答題時間：</b>每題有 10 秒倒數時間（影片題會先播放完畢才開始倒數且才能點選選項）。</p>
                <p><b>2. 計分方式：</b>答對獲得題目基礎分 + 剩餘時間加分；答錯不倒扣。</p>
                <p><b>3. 題型種類：</b>包含文字題、圖片題以及影片題。</p>
            </div>
            <button class="btn-submit" onclick="closeRulesModal()" style="margin-top:15px;">返回主頁</button>
        </div>
    </div>
    
    <!-- 💡 排行榜彈窗 -->
    <div id="leaderboard-modal" class="modal-overlay hidden">
        <div class="modal-content" style="max-width: 450px;">
            <h2 style="color:#ff2a75; margin-bottom:15px; text-align:center;">🏆 排行榜 (TOP 30)</h2>
            <div style="max-height: 300px; overflow-y: auto;">
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>名次</th>
                            <th>名稱</th>
                            <th>本命</th>
                            <th>答對題數</th>
                            <th>分數</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboard-body">
                        <!-- 動態插入排行榜 -->
                    </tbody>
                </table>
            </div>
            <button class="btn-submit" onclick="closeLeaderboardModal()" style="margin-top:15px;">返回主頁</button>
        </div>
    </div>
    
    <!-- 💡 彩蛋影片彈窗（修改 src 載入方式） -->
    <div id="bang-modal" class="modal-overlay hidden">
        <div class="modal-content" style="max-width: 420px; position: relative; padding: 15px;">
            <button onclick="closeBangModal()" style="position: absolute; top: 8px; right: 12px; background: none; border: none; color: #ff2a75; font-size: 24px; font-weight: bold; cursor: pointer; z-index: 10;">✖</button>
            <video id="bang-video" src="{{ url_for('static', filename='bang.mp4') }}" style="width: 100%; border-radius: 10px; margin-top: 15px;" controls playsinline>
                您的瀏覽器不支援影片播放。
            </video>
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

    // 💡 1-1. 新增排行榜彈窗開關與資料接收函式
    function openLeaderboardModal() {
        socket.emit('get_leaderboard');
        document.getElementById('leaderboard-modal').classList.remove('hidden');
    }

    function closeLeaderboardModal() {
        document.getElementById('leaderboard-modal').classList.add('hidden');
    }
    
    // 💡 請貼在這裡（彩蛋影片彈窗開關控制）
    function openBangModal() {
        const bgm = document.getElementById('lobby-bgm');
        const bangVideo = document.getElementById('bang-video');
        
        // 1. 暫停 BGM
        if (bgm && !bgm.paused) {
            bgm.pause();
        }
        
        // 2. 顯示 Modal 並從頭播放影片
        document.getElementById('bang-modal').classList.remove('hidden');
        if (bangVideo) {
            bangVideo.currentTime = 0;
            bangVideo.play().catch(err => console.log("影片自動播放受限:", err));
            
            // 💡 影片播放結束時自動關閉並繼續背景音樂
            bangVideo.onended = closeBangModal;
        }
    }

    function closeBangModal() {
        const bgm = document.getElementById('lobby-bgm');
        const bangVideo = document.getElementById('bang-video');
        
        // 1. 暫停影片
        if (bangVideo) {
            bangVideo.pause();
        }
        
        // 2. 隱藏 Modal
        document.getElementById('bang-modal').classList.add('hidden');
        
        // 3. 恢復 BGM 續播（從剛才斷掉的地方繼續）
        if (bgm && isMusicPlaying) {
            bgm.play().catch(err => console.log("背景音樂恢復受限:", err));
        }
    }

    // 接收並渲染主頁排行榜 Modal 資料
    socket.on('update_leaderboard', (data) => {
        let html = "";
        if (data.leaderboard && data.leaderboard.length > 0) {
            data.leaderboard.forEach((p, index) => {
                html += `<tr>
                    <td>${index + 1}</td>
                    <td><b>${p.name}</b></td>
                    <td>${p.bias}</td>
                    <td>${p.correct_count || 0} 題</td>
                    <td style="color:#ff2a75; font-weight:bold;">${p.score}</td>
                </tr>`;
            });
        } else {
            html = "<tr><td colspan='5'>暫無紀錄</td></tr>";
        }
        document.getElementById('leaderboard-body').innerHTML = html;
    });

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
        const savedAge = sessionStorage.getItem('quiz_age') || '未提供'; // 💡 1. 讀取年齡快取

        if (savedName) {
            document.getElementById('username').value = savedName;
            myName = savedName;
            
            if (savedBias) {
                const biasRadio = document.querySelector(`input[name="bias"][value="${savedBias}"]`);
                if (biasRadio) biasRadio.checked = true;
            }

            // 💡 2. 若有暫存年齡，順便自動填入 input 欄位
            if (savedAge !== '未提供') {
                document.getElementById('user-age').value = savedAge;
            }

            // 💡 3. 將包含 age 的完整資料發送給後端
            socket.emit('join_room', { name: savedName, bias: savedBias || 'Ruka', age: savedAge });
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
        const myAge = document.getElementById('user-age').value.trim();
        const biasEl = document.querySelector('input[name="bias"]:checked');
        const bias = biasEl ? biasEl.value : 'Ruka';

        if (!myName) return alert("請輸入暱稱！");
        if (!myAge) return alert("請輸入年齡！");

        sessionStorage.setItem('quiz_username', myName);
        sessionStorage.setItem('quiz_bias', bias);
        sessionStorage.setItem('quiz_age', myAge);

        const bgm = document.getElementById('lobby-bgm');
        if (bgm && isMusicPlaying && bgm.paused) {
            bgm.volume = 0.4;
            bgm.play().catch(err => console.log("音樂播放受限:", err));
        }

        socket.emit('join_room', { name: myName, bias: bias, age: myAge });
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
                <span id="timer-text" style="color:#ff758c; font-weight:bold;">📖 閱讀題目中...</span>
            </div>
            <div class="timer-container"><div id="timer-bar" class="timer-bar" style="width: 100%; background: #ff758c;"></div></div>
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
            // 💡 停頓 1 秒期間保持粉紅色提示，1 秒過後恢復桃紅色並啟動倒數
            setTimeout(() => {
                const bar = document.getElementById('timer-bar');
                if (bar) bar.style.background = '#ff2a75';
                startTimer(q.answer);
            }, 1000);
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
    
    let myInfo = data.my_result ? data.my_result[0] : null;
    let html = `<h2 style="color:#ff2a75; text-align:center; margin-bottom:10px;">🏆 挑戰結束</h2>`;
    
    // 💡 1. 顯示玩家個人成績（包含答對題數與最終得分）
    if (myInfo) {
        html += `<div class="roster-item" style="text-align:center; margin-bottom:15px; padding: 12px;">
            答對題數：<b style="color:#10b981; font-size:16px;">${myInfo.correct_count || 0}</b> 題<br>
            最終得分：<span style="color:#ff2a75; font-weight:bold; font-size:20px;">${myInfo.score || 0}</span> 分
        </div>`;
    }

    // 💡 2. 結算畫面直接嵌入 TOP 30 排行榜表格
    html += `<h4 style="color:#fff; margin-bottom:8px; text-align:center;">📊 排行榜 TOP 30</h4>`;
    html += `<div style="max-height: 220px; overflow-y: auto;">
        <table class="leaderboard-table">
            <thead>
                <tr>
                    <th>名次</th><th>名稱</th><th>本命</th><th>答對題數</th><th>分數</th>
                </tr>
            </thead>
            <tbody>`;
            
    if (data.leaderboard && data.leaderboard.length > 0) {
        data.leaderboard.forEach((p, index) => {
            html += `<tr>
                <td>${index + 1}</td>
                <td><b>${p.name}</b></td>
                <td>${p.bias}</td>
                <td>${p.correct_count || 0} 題</td>
                <td style="color:#ff2a75; font-weight:bold;">${p.score}</td>
            </tr>`;
        });
    } else {
        html += `<tr><td colspan="5">暫無紀錄</td></tr>`;
    }
    
    html += `</tbody></table></div>`;
    html += `<button class="btn-submit" onclick="restartGame()" style="margin-top:15px;">🔄 再次挑戰</button>`;
    
    document.getElementById('quiz-box').innerHTML = html;
});

// 💡 3. 保留你的 restartGame 函式
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
    age = data.get('age', '未提供')  # 💡 接收年齡
    
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
        # 💡 新增 age 與 correct_count (答對題數)
        r['players'].append({"name": name, "bias": bias, "age": age, "score": 0, "correct_count": 0})
    else:
        player['bias'] = bias
        player['age'] = age

    if r['status'] == "PLAYING":
        q_idx = r['current_q']
        if q_idx < len(r['selected_questions']):
            emit('new_question', {
                "question": r['selected_questions'][q_idx],
                "index": q_idx,
                "total": len(r['selected_questions'])
            }, room=room)
            return

    emit('room_assigned', {"room": room, "players": r['players']}, room=room)

@socketio.on('start_game')
def handle_start(data):
    room = data.get('room')
    
    if room and room in ROOMS:
        r = ROOMS[room]
        r['status'] = "PLAYING"
        r['current_q'] = 0
        
        for p in r['players']:
            p['score'] = 0
            p['correct_count'] = 0
            
        q1_sample = random.sample(QUESTION1, min(7, len(QUESTION1)))
        q2_sample = random.sample(QUESTION2, min(7, len(QUESTION2)))
        q3_sample = random.sample(QUESTION3, min(5, len(QUESTION3)))
        pic_sample = random.sample(QUESTION_PICTURE, min(7, len(QUESTION_PICTURE)))
        vid_sample = random.sample(QUESTION_VIDEO, min(4, len(QUESTION_VIDEO)))

        # 💡 1. 拷貝前直接為各題型注入分數權重
        for q in q1_sample: q['base_score'] = 100
        for q in q2_sample: q['base_score'] = 150
        for q in q3_sample: q['base_score'] = 200
        for q in pic_sample: q['base_score'] = 150
        for q in vid_sample: q['base_score'] = 150

        # 💡 2. 將設定好分數的題目合併並進行深拷貝
        selected_raw = copy.deepcopy(q1_sample + q2_sample + q3_sample + pic_sample + vid_sample)

        # 💡 3. 打亂選項與題目順序
        for q in selected_raw:
            if 'options' in q and isinstance(q['options'], list):
                random.shuffle(q['options'])

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
        
        # 1. 將本局玩家寫入全域排行榜
        for p in r['players']:
            GLOBAL_LEADERBOARD.append(copy.deepcopy(p))
            
        # 💡 2. 自動寫入 JSON 檔案（確保伺服器重啟或重新部署時資料不丟失）
        try:
            with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
                json.dump(GLOBAL_LEADERBOARD, f, ensure_ascii=False, indent=2)
            print("💾 排行榜資料已成功儲存至 leaderboard.json！")
        except Exception as e:
            print(f"⚠️ 儲存排行榜檔案失敗: {e}")

        # 3. 印出所有歷史玩家紀錄（包含年齡）至後台控制台 Log
        print("=== 當前所有玩家紀錄 ===")
        for p in GLOBAL_LEADERBOARD:
            print(f"姓名: {p['name']}, 年齡: {p.get('age', '未提供')}, 本命: {p['bias']}, 答對: {p.get('correct_count', 0)}, 得分: {p['score']}")

        # 4. 依照分數排序全域榜單，取前 30 名發給前端
        sorted_global = sorted(GLOBAL_LEADERBOARD, key=lambda x: x['score'], reverse=True)
        top_30 = sorted_global[:30]
        
        emit('game_over', {
            "leaderboard": top_30, 
            "my_result": r['players']
        }, room=room)

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
        
        for p in r['players']:
            if p['name'] == name:
                if is_correct:
                    # 1. 計算並累加得分
                    earned_score = base_score + int(time_left * 10)
                    p['score'] += earned_score
                    
                    # 💡 2. 累計答對題數（確保欄位存在，若無則預設為 0 再加 1）
                    p['correct_count'] = p.get('correct_count', 0) + 1

        # 推進至下一題
        r['current_q'] += 1
        send_question(room)

# 💡 新增主頁查詢排行榜事件
@socketio.on('get_leaderboard')
def handle_get_leaderboard():
    sorted_global = sorted(GLOBAL_LEADERBOARD, key=lambda x: x['score'], reverse=True)
    emit('update_leaderboard', {"leaderboard": sorted_global[:30]})
    
if __name__ == '__main__':
    print("🚀 BABYMONSTER 伺服器啟動中...")
    print("👉 請開啟網址: http://127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)