// CoachEduAI - Main JavaScript

// Global Variables
let currentUser = null;
let socket = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// Main initialization function
function initializeApp() {
    // Initialize tooltips and popovers
    initializeBootstrapComponents();

    // Initialize form validation
    initializeFormValidation();

    // Initialize search functionality
    initializeSearch();

    // Initialize real-time features
    initializeRealTime();

    // Initialize animations
    initializeAnimations();
}

// Bootstrap Components
function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Form Validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');

    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}

// Search Functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input');

    searchInputs.forEach(input => {
        input.addEventListener('input', debounce(function(e) {
            performSearch(e.target.value, e.target.dataset.searchType);
        }, 300));
    });
}

// Debounce function for search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Perform search
function performSearch(query, type) {
    if (query.length < 2) return;

    const searchResults = document.getElementById('searchResults');
    if (!searchResults) return;

    // Show loading
    searchResults.innerHTML = '<div class="text-center"><div class="loading-spinner"></div> Đang tìm kiếm...</div>';

    // Simulate API call
    setTimeout(() => {
        // This would be replaced with actual API call
        searchResults.innerHTML = `<div class="alert alert-info">Kết quả tìm kiếm cho: "${query}"</div>`;
    }, 500);
}

// Real-time Features
function initializeRealTime() {
    // Check if user is logged in
    if (window.CURRENT_USER_ID) {
        // Initialize Socket.IO for real-time features
        if (typeof io !== 'undefined') {
            socket = io();

            // Join user's notification room
            socket.emit('join_notifications');

            // Listen for notifications
            socket.on('new_notification', function(data) {
                showNotification(data.content || data, 'info');
                updateNotificationBadge();
            });

            // Listen for chat messages
            socket.on('new_message', function(data) {
                if (window.location.pathname.includes('/chat')) {
                    displayChatMessage(data);
                }
            });
        }
    }
}

// Notifications
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.toast-notification');
    existingNotifications.forEach(n => n.remove());

    // Create new notification
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} position-fixed toast-notification`;
    notification.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border: none;
    `;
    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${getIconForType(type)} me-2"></i>
            <div>${message}</div>
            <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

function getIconForType(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-triangle',
        'warning': 'exclamation-circle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Update notification badge
function updateNotificationBadge() {
    const badge = document.querySelector('.notification-badge');
    if (badge) {
        let count = parseInt(badge.textContent) || 0;
        badge.textContent = count + 1;
        badge.style.display = 'inline';
    }
}

// Chat Functions
function displayChatMessage(data) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${data.sender_id === window.CURRENT_USER_ID ? 'message-sent' : 'message-received'}`;
    messageDiv.innerHTML = `
        <div class="message-content">${data.content}</div>
        <div class="message-time">${formatTime(data.timestamp)}</div>
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message) return;

    if (socket) {
        socket.emit('send_message', {
            content: message,
            room: getCurrentChatRoom()
        });
    }

    input.value = '';
}

function getCurrentChatRoom() {
    // Determine current chat room based on URL or context
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1] || 'general';
}

// Exercise Functions
function startExercise(exerciseId) {
    // Record start time
    const startTime = new Date().toISOString();
    sessionStorage.setItem(`exercise_${exerciseId}_start`, startTime);

    // Show timer if needed
    const timer = document.getElementById('exerciseTimer');
    if (timer) {
        startTimer(timer);
    }
}

function submitExercise(exerciseId) {
    const answer = document.getElementById('exerciseAnswer').value.trim();

    if (!answer) {
        showNotification('Vui lòng nhập đáp án', 'warning');
        return;
    }

    // Calculate time taken
    const startTime = sessionStorage.getItem(`exercise_${exerciseId}_start`);
    const timeTaken = startTime ? Math.floor((new Date() - new Date(startTime)) / 1000) : 0;

    // Submit to server
    fetch('/api/submit_exercise', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            exercise_id: exerciseId,
            answer: answer,
            time_taken: timeTaken
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(`Chính xác! Bạn được ${data.score} điểm`, 'success');
            updateUserScore(data.score);
            // Update UI or refresh ranking
            setTimeout(() => location.reload(), 2000);
        } else {
            showNotification('Đáp án chưa chính xác. Hãy thử lại!', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Có lỗi xảy ra. Vui lòng thử lại!', 'error');
    });
}

// Timer Functions
function startTimer(timerElement, duration = null) {
    if (!duration) {
        // Count up timer
        let seconds = 0;
        const interval = setInterval(() => {
            seconds++;
            timerElement.textContent = formatDuration(seconds);
        }, 1000);

        timerElement.dataset.interval = interval;
    } else {
        // Count down timer
        let remainingTime = duration;
        const interval = setInterval(() => {
            remainingTime--;
            timerElement.textContent = formatDuration(remainingTime);

            if (remainingTime <= 0) {
                clearInterval(interval);
                onTimerExpired();
            }
        }, 1000);

        timerElement.dataset.interval = interval;
    }
}

function stopTimer(timerElement) {
    const interval = timerElement.dataset.interval;
    if (interval) {
        clearInterval(interval);
    }
}

function onTimerExpired() {
    showNotification('Hết thời gian!', 'warning');
    // Auto-submit or disable form
}

// Utility Functions
function formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString('vi-VN');
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function updateUserScore(newScore) {
    const scoreElement = document.querySelector('.user-score');
    if (scoreElement) {
        const currentScore = parseInt(scoreElement.textContent) || 0;
        scoreElement.textContent = currentScore + newScore;

        // Add animation
        scoreElement.classList.add('text-success');
        setTimeout(() => {
            scoreElement.classList.remove('text-success');
        }, 2000);
    }
}

// Animations
function initializeAnimations() {
    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
            }
        });
    }, observerOptions);

    // Observe elements with animation class
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

// Contest Functions
function joinContest(contestId) {
    if (!confirm('Bạn có chắc chắn muốn tham gia cuộc thi này?')) {
        return;
    }

    fetch('/api/join_contest', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            contest_id: contestId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            // Update button state
            const button = document.querySelector(`button[onclick="joinContest(${contestId})"]`);
            if (button) {
                button.innerHTML = '<i class="fas fa-check me-2"></i>Đã tham gia';
                button.disabled = true;
                button.className = 'btn btn-success btn-lg';
            }
        } else {
            showNotification('Lỗi: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Có lỗi xảy ra khi tham gia cuộc thi!', 'danger');
    });
}

// Group Functions
function joinGroup(groupId) {
    fetch('/api/join_group', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ group_id: groupId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Đã gửi yêu cầu tham gia nhóm!', 'success');
        } else {
            showNotification(data.message || 'Có lỗi xảy ra', 'error');
        }
    });
}

// Export functions for global use
window.CoachEduAI = {
    showNotification,
    startExercise,
    submitExercise,
    joinContest,
    joinGroup,
    sendChatMessage
};

// New functions based on the changes provided
// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize search functionality
    initializeSearch();

    // Initialize real-time ranking updates
    initializeRanking();

    // Initialize auto-save
    initializeAutoSave();
});

// Search functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input');

    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const searchType = this.dataset.searchType;
            const query = this.value.toLowerCase();

            if (searchType === 'exercises') {
                filterExercises(query);
            } else if (searchType === 'contests') {
                filterContests(query);
            }
        });
    });
}

function filterExercises(query) {
    const exerciseCards = document.querySelectorAll('.exercise-card');

    exerciseCards.forEach(card => {
        const title = card.querySelector('.card-title').textContent.toLowerCase();
        const content = card.querySelector('.card-text').textContent.toLowerCase();

        if (title.includes(query) || content.includes(query)) {
            card.closest('.col-md-6, .col-lg-4').style.display = '';
        } else {
            card.closest('.col-md-6, .col-lg-4').style.display = 'none';
        }
    });
}

function filterContests(query) {
    const contestCards = document.querySelectorAll('.contest-card');

    contestCards.forEach(card => {
        const title = card.querySelector('.card-title').textContent.toLowerCase();
        const description = card.querySelector('.card-text').textContent.toLowerCase();

        if (title.includes(query) || description.includes(query)) {
            card.closest('.col-md-6, .col-lg-4').style.display = '';
        } else {
            card.closest('.col-md-6, .col-lg-4').style.display = 'none';
        }
    });
}

// Real-time ranking functionality
function initializeRanking() {
    if (typeof io !== 'undefined') {
        const socket = io();

        socket.on('connect', function() {
            console.log('Connected to ranking updates');
            socket.emit('join_ranking');
        });

        socket.on('ranking_update', function(data) {
            updateRankingTable(data.subject, data.rankings);
        });
    }
}

function updateRankingTable(subject, rankings) {
    const table = document.querySelector('#ranking-table-' + subject);
    if (!table) return;

    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    rankings.forEach((user, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <span class="badge ${getRankBadgeClass(user.rank)}">${user.rank}</span>
            </td>
            <td>
                <div class="d-flex align-items-center">
                    <img src="/static/img/default-avatar.png" class="rounded-circle me-2" width="32" height="32">
                    <div>
                        <div class="fw-medium">${user.full_name}</div>
                        <small class="text-muted">${user.school || 'Chưa cập nhật'}</small>
                    </div>
                </div>
            </td>
            <td><span class="h6 text-success mb-0">${user.score}</span></td>
            <td><span class="text-muted">${user.exercises_solved} bài</span></td>
            <td><span class="text-muted">${user.city || 'Chưa cập nhật'}</span></td>
        `;
        tbody.appendChild(row);
    });
}

function getRankBadgeClass(rank) {
    if (rank === 1) return 'bg-warning';
    if (rank === 2) return 'bg-secondary';
    if (rank === 3) return 'bg-danger';
    return 'bg-primary';
}

// Auto-save functionality
function initializeAutoSave() {
    setInterval(() => {
        fetch('/api/auto_save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Auto-save successful:', data.timestamp);
            }
        })
        .catch(error => {
            console.log('Auto-save error:', error);
        });
    }, 30000); // Auto-save every 30 seconds
}

// Exercise functionality
const CoachEduAI = {
    currentExerciseId: null,
    exerciseStartTime: null,

    startExercise: function(exerciseId) {
        this.currentExerciseId = exerciseId;
        this.exerciseStartTime = new Date();
        this.startTimer();
    },

    startTimer: function() {
        const timerElement = document.getElementById('exerciseTimer');
        if (!timerElement) return;

        setInterval(() => {
            if (this.exerciseStartTime) {
                const elapsed = Math.floor((new Date() - this.exerciseStartTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                timerElement.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }
        }, 1000);
    },

    submitExercise: function(exerciseId) {
        const answer = document.getElementById('exerciseAnswer').value;

        if (!answer.trim()) {
            showNotification('Vui lòng nhập đáp án!', 'warning');
            return;
        }

        fetch('/api/submit_exercise', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                exercise_id: exerciseId,
                answer: answer
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, data.is_correct ? 'success' : 'warning');
                if (data.is_correct) {
                    // Update UI or refresh ranking
                    setTimeout(() => location.reload(), 2000);
                }
            } else {
                showNotification('Lỗi: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Có lỗi xảy ra khi nộp bài!', 'danger');
        });
    }
};

// Contest functionality
function joinContest(contestId) {
    if (!confirm('Bạn có chắc chắn muốn tham gia cuộc thi này?')) {
        return;
    }

    fetch('/api/join_contest', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            contest_id: contestId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            // Update button state
            const button = document.querySelector(`button[onclick="joinContest(${contestId})"]`);
            if (button) {
                button.innerHTML = '<i class="fas fa-check me-2"></i>Đã tham gia';
                button.disabled = true;
                button.className = 'btn btn-success btn-lg';
            }
        } else {
            showNotification('Lỗi: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Có lỗi xảy ra khi tham gia cuộc thi!', 'danger');
    });
}

// Score update functionality
function updateScore(subject, points) {
    fetch('/api/add_score', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            subject: subject,
            score: points
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(`Bạn được ${points} điểm!`, 'success');
        }
    })
    .catch(error => {
        console.error('Score update error:', error);
    });
}