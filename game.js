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

let debugMessage = "";

/**
 * Builds a guaranteed-playable level algorithmically.
 * Platforms form a step-by-step path from spawn to goal within jump physics limits.
 * Max jump: ~150px horizontal, ~110px vertical.
 */
function buildLevel(theme, style) {
    const CANVAS_W = 800;
    const CANVAS_H = 600;
    const MAX_JUMP_X = 140;  // slightly under physics limit for fairness
    const MAX_JUMP_Y = 90;   // max vertical rise per step
    const PLAT_H = 14;
    const LAUNCH_ZONE = 45;  // right side of every platform: always lava-free (jump-off zone)

    const platforms = [];
    const lavaZones = [];

    // Starting platform — player spawns at (50, 550). No lava here.
    platforms.push({ x: 0, y: 568, w: 130, h: 20 });

    let curX = 130;  // right edge of last platform
    let curY = 568;  // top of last platform
    let step = 0;
    const targetSteps = 16 + Math.floor(Math.random() * 4); // 16-19 steps

    while (step < targetSteps && curX < CANVAS_W - 60) {
        // Gaps: 75–140px — always beatable but requires commitment
        const gapX = 75 + Math.floor(Math.random() * (MAX_JUMP_X - 75));

        // Vertical: mostly upward, occasional reset drops — but not both huge at once
        const roll = Math.random();
        let deltaY;
        if (roll < 0.55) deltaY = -(30 + Math.floor(Math.random() * MAX_JUMP_Y));   // rise (30-120px)
        else if (roll < 0.75) deltaY = -(10 + Math.floor(Math.random() * 25));       // small rise
        else if (roll < 0.90) deltaY = 30 + Math.floor(Math.random() * 70);          // drop to reset
        else deltaY = 0;                                                               // flat

        const newX = curX + gapX;
        let newY = curY + deltaY;

        newY = Math.max(60, Math.min(CANVAS_H - 60, newY));
        if (newX > CANVAS_W - 50) break;

        // Platforms: 90 to 130px wide
        const platW = 90 + Math.floor(Math.random() * 40);
        platforms.push({ x: newX, y: newY, w: platW, h: PLAT_H });

        // Lava in the floor gap between platforms
        if (gapX > 20 && newX > 150) {
            lavaZones.push({ x: curX + 4, y: 582, w: gapX - 8, h: 18 });
        }

        // ~30% chance: on-platform lava on the LEFT end only.
        // The RIGHT side (LAUNCH_ZONE) is ALWAYS safe so the player can always jump off.
        if (Math.random() < 0.30 && platW > LAUNCH_ZONE + 40) {
            const lavaW = platW - LAUNCH_ZONE;
            // Lava always on left — forces precise right-side landing, right side free to jump
            lavaZones.push({ x: newX, y: newY - 14, w: lavaW, h: 14 + PLAT_H });
        }

        curX = newX + platW;
        curY = newY;
        step++;
    }

    // Goal above the right side of the last platform (in the safe zone)
    const lastPlat = platforms[platforms.length - 1];
    const goal = {
        x: lastPlat.x + lastPlat.w - LAUNCH_ZONE + 2,
        y: lastPlat.y - 50
    };

    return { platforms, lava: lavaZones, goal, theme };
}

async function initGame() {
    gameState = 'loading';
    uiController.showLoading(true);
    
    const levelData = await generateLevel();
    platforms = levelData.platforms || [];
    lava = levelData.lava || [];
    goal = { ...levelData.goal, w: 40, h: 40 };
    player.color = levelData.theme.primary;
    debugMessage = levelData.theme.name; // Capture fallback error
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
    
    // Draw Theme/Debug Message
    if (debugMessage) {
        ctx.fillStyle = '#ffcc00';
        ctx.font = '16px monospace';
        ctx.fillText(debugMessage, 10, 30);
    }
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
