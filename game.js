const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

canvas.width = 800;
canvas.height = 600;

const player = {
    x: 50,
    y: 500,
    w: 30,
    h: 30,
    vx: 0,
    vy: 0,
    speed: 5,
    jump: -12,
    gravity: 0.6,
    grounded: false,
    color: '#fff'
};

let platforms = [];
let lava = [];
let goal = { x: 750, y: 100, w: 40, h: 40 };
let gameState = 'loading'; // loading, playing, won, lost

const keys = {};

window.addEventListener('keydown', e => keys[e.code] = true);
window.addEventListener('keyup', e => keys[e.code] = false);

async function initGame() {
    gameState = 'loading';
    uiController.showLoading(true);
    
    const levelData = await generateLevel();
    platforms = levelData.platforms || [];
    lava = levelData.lava || [];
    goal = { ...levelData.goal, w: 40, h: 40 };
    player.color = levelData.theme.primary;
    player.x = 50;
    player.y = 550;
    
    document.body.style.backgroundColor = levelData.theme.bg;
    
    gameState = 'playing';
    uiController.showLoading(false);
    uiController.showHUD(true);
    
    gameLoop();
}

function update() {
    if (gameState !== 'playing') return;

    if (keys['ArrowRight']) player.vx = player.speed;
    else if (keys['ArrowLeft']) player.vx = -player.speed;
    else player.vx = 0;

    if (keys['ArrowUp'] && player.grounded) {
        player.vy = player.jump;
        player.grounded = false;
    }

    player.vy += player.gravity;
    player.x += player.vx;
    player.y += player.vy;

    // Boundary check
    if (player.x < 0) player.x = 0;
    if (player.x + player.w > canvas.width) player.x = canvas.width - player.w;
    
    // Death check (fall off)
    if (player.y > canvas.height) {
        die();
    }

    // Lava collision
    lava.forEach(l => {
        if (player.x < l.x + l.w &&
            player.x + player.w > l.x &&
            player.y < l.y + l.h &&
            player.y + player.h > l.y) {
            die();
        }
    });

    player.grounded = false;

    // Platform collision
    platforms.forEach(p => {
        if (player.x < p.x + p.w &&
            player.x + player.w > p.x &&
            player.y < p.y + p.h &&
            player.y + player.h > p.y) {
            
            // Resolve from top
            // Check if player was above the platform top in the previous frame
            if (player.vy >= 0 && (player.y + player.h - player.vy) <= p.y + 15) {
                player.y = p.y - player.h;
                player.vy = 0;
                player.grounded = true;
            } else if (player.vy < 0) {
                player.y = p.y + p.h;
                player.vy = 0;
            }
        }
    });

    // Goal collision
    if (player.x < goal.x + goal.w &&
        player.x + player.w > goal.x &&
        player.y < goal.y + goal.h &&
        player.y + player.h > goal.y) {
        win();
    }
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw platforms
    ctx.fillStyle = player.color;
    platforms.forEach(p => {
        ctx.fillRect(p.x, p.y, p.w, p.h);
        // Subtle glow
        ctx.shadowBlur = 10;
        ctx.shadowColor = player.color;
    });
    ctx.shadowBlur = 0;

    // Draw Lava
    ctx.fillStyle = '#ff4400';
    lava.forEach(l => {
        ctx.fillRect(l.x, l.y, l.w, l.h);
        ctx.shadowBlur = 15;
        ctx.shadowColor = '#ff4400';
    });
    ctx.shadowBlur = 0;

    // Draw Goal
    ctx.fillStyle = '#ffcc00';
    ctx.shadowColor = '#ffcc00';
    ctx.fillRect(goal.x, goal.y, goal.w, goal.h);
    
    // Draw Player
    ctx.fillStyle = '#fff';
    ctx.shadowBlur = 15;
    ctx.shadowColor = '#fff';
    ctx.fillRect(player.x, player.y, player.w, player.h);
    
    ctx.shadowBlur = 0;
}

function gameLoop() {
    if (gameState === 'playing') {
        update();
        draw();
        requestAnimationFrame(gameLoop);
    }
}

function win() {
    gameState = 'won';
    uiController.showWin(true);
}

function giveUp() {
    gameState = 'lost';
    uiController.flashLoser();
}

function die() {
    // Restart position
    player.x = 50;
    player.y = 550;
    player.vx = 0;
    player.vy = 0;
    player.grounded = false;
}

initGame();
