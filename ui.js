const uiController = {
    showLoading: (show) => {
        document.getElementById('loading-screen').classList.toggle('hidden', !show);
    },
    showHUD: (show) => {
        document.getElementById('hud').classList.toggle('hidden', !show);
    },
    showWin: (show) => {
        document.getElementById('win-panel').classList.toggle('hidden', !show);
        uiController.showHUD(false);
    },
    flashLoser: async () => {
        uiController.showHUD(false);
        const loser = document.getElementById('loser-text');
        loser.classList.remove('hidden');
        
        // Wait 2 seconds for flash
        await new Promise(r => setTimeout(r, 2000));
        
        loser.classList.add('hidden');
        uiController.exitToBrowser();
    },
    exitToBrowser: () => {
        document.getElementById('game-overlay').style.display = 'none';
        document.getElementById('search-input').focus();
    }
};

document.getElementById('give-up-btn').onclick = () => {
    giveUp();
};

document.getElementById('close-btn').onclick = () => {
    uiController.exitToBrowser();
};

document.getElementById('restart-btn').onclick = () => {
    location.reload();
};

// Search handling
document.getElementById('search-input').onkeydown = (e) => {
    if (e.key === 'Enter') {
        const query = e.target.value;
        window.location.href = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
    }
};

document.querySelectorAll('.shortcut-item').forEach(item => {
    item.onclick = () => {
        const title = item.getAttribute('title').toLowerCase();
        window.location.href = `https://www.${title}.com`;
    };
});
