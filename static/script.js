// Función para iniciar el chat desde el hero
function startChat(event) {
    event.preventDefault();
    
    const input = document.getElementById('hero-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Animar la desaparición del contenido hero
    const heroContent = document.getElementById('hero-content');
    const heroAvatar = document.getElementById('hero-avatar');
    const heroAvatarMobile = document.getElementById('hero-avatar-mobile');
    const heroTitle = document.getElementById('hero-title');
    
    // Aplicar animación de fade out al contenido y título
    heroContent.classList.add('fade-out-up');
    heroTitle.classList.add('fade-out-up');
    
    // Aplicar animación de reducción a los avatares (desktop y mobile)
    if (heroAvatar) {
        heroAvatar.classList.add('shrink-avatar');
    }
    if (heroAvatarMobile) {
        heroAvatarMobile.classList.add('fade-out-up');
    }
    
    // Esperar a que termine la animación (0.8s)
    setTimeout(() => {
        // Cambiar a la vista de chat
        document.getElementById('home-section').classList.add('hidden');
        const chatSection = document.getElementById('chat-section');
        chatSection.classList.remove('hidden');
        // No aplicar animación de entrada (fade-in-chat removido)
        
        // Agregar mensaje de bienvenida del bot
        addMessage('¡Hola! 👋 Soy MediNutrIA, tu asistente de salud y nutrición. Vi tu pregunta, déjame ayudarte.', 'bot');
        
        // Agregar el mensaje del usuario
        addMessage(message, 'user');
        
        // Mostrar indicador de escritura
        showTypingIndicator();
        
        // Enviar el mensaje a la API
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            removeTypingIndicator();
            addMessage(data.response, 'bot');
        })
        .catch(error => {
            console.error('Error:', error);
            removeTypingIndicator();
            addMessage('Lo siento, ha ocurrido un error. Por favor, intenta nuevamente.', 'bot');
        });
        
        // Limpiar el input del hero
        input.value = '';
        
        // Remover las clases de animación para futuros usos
        heroContent.classList.remove('fade-out-up');
        heroTitle.classList.remove('fade-out-up');
        if (heroAvatar) {
            heroAvatar.classList.remove('shrink-avatar');
        }
        if (heroAvatarMobile) {
            heroAvatarMobile.classList.remove('fade-out-up');
        }
    }, 800); // Sincronizado con la duración de 0.8s de las nuevas animaciones
}

// Función para mostrar la página de inicio
function showHome() {
    document.getElementById('home-section').classList.remove('hidden');
    document.getElementById('chat-section').classList.add('hidden');
    // Limpiar mensajes del chat
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
}

// Función para mostrar el chatbot (solo se usa si ya hay conversación)
function showChat() {
    document.getElementById('home-section').classList.add('hidden');
    document.getElementById('chat-section').classList.remove('hidden');
}

// Función para enviar mensajes
async function sendMessage(event) {
    event.preventDefault();
    
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Agregar mensaje del usuario
    addMessage(message, 'user');
    input.value = '';
    
    // Mostrar indicador de escritura
    showTypingIndicator();
    
    try {
        // Llamar a la API de FastAPI
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        
        // Remover indicador de escritura
        removeTypingIndicator();
        
        // Agregar respuesta del bot
        addMessage(data.response, 'bot');
        
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator();
        addMessage('Lo siento, ha ocurrido un error. Por favor, intenta nuevamente.', 'bot');
    }
}

// Función para agregar mensajes al chat
function addMessage(text, sender) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message flex items-start space-x-3';
    
    if (sender === 'user') {
        messageDiv.classList.add('flex-row-reverse', 'space-x-reverse');
        messageDiv.innerHTML = `
            <div class="w-12 h-12 bg-gray-300 rounded-full flex items-center justify-center text-2xl flex-shrink-0">
                👤
            </div>
            <div class="bg-blue-600 text-white rounded-2xl rounded-tr-none p-5 shadow-md max-w-xl">
                <p class="text-lg">${escapeHtml(text)}</p>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="w-12 h-12 flex items-center justify-center flex-shrink-0">
                <img src="/static/logo.png" alt="MediNutrIA" class="w-full h-full object-contain">
            </div>
            <div class="bg-white rounded-2xl rounded-tl-none p-5 shadow-md max-w-xl">
                <p class="text-gray-800 text-lg">${escapeHtml(text)}</p>
            </div>
        `;
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Mostrar indicador de escritura
function showTypingIndicator() {
    const chatMessages = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.className = 'chat-message flex items-start space-x-3';
    typingDiv.innerHTML = `
        <div class="w-12 h-12 flex items-center justify-center flex-shrink-0">
            <img src="/static/logo.png" alt="MediNutrIA" class="w-full h-full object-contain">
        </div>
        <div class="bg-white rounded-2xl rounded-tl-none p-5 shadow-md">
            <div class="flex space-x-2">
                <div class="w-3 h-3 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0s"></div>
                <div class="w-3 h-3 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                <div class="w-3 h-3 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remover indicador de escritura
function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Función para escapar HTML y prevenir XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Permitir enviar con Enter
document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('user-input');
    if (input) {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                document.getElementById('chat-form').dispatchEvent(new Event('submit'));
            }
        });
    }
});
