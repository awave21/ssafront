// Тестовый скрипт для проверки структуры ответа API
// Запуск: node test-auth-api.js
// Процесс:
// 1. Вход через email/пароль → получение JWT токена
// 2. Создание API ключа через JWT токен
// 3. Получение токена по созданному API ключу
// 4. Проверка наличия refresh_token во всех ответах

// Проверка версии Node.js и наличие fetch
const nodeVersion = process.version;
const majorVersion = parseInt(nodeVersion.split('.')[0].substring(1));

if (majorVersion < 18) {
  console.error('❌ Требуется Node.js версии 18 или выше!');
  console.error(`   Текущая версия: ${nodeVersion}`);
  console.error('   Установите новую версию: https://nodejs.org/\n');
  process.exit(1);
}

// Импорт fetch для старых версий (если нужно)
let fetch;
if (typeof globalThis.fetch === 'undefined') {
  try {
    fetch = require('node-fetch');
  } catch (e) {
    console.error('❌ fetch не доступен. Установите: npm install node-fetch');
    process.exit(1);
  }
} else {
  fetch = globalThis.fetch;
}

const API_BASE = 'https://agentsapp.integration-ai.ru/api/v1';
const EMAIL = 'moskovets.maksim@yandex.ru';
const PASSWORD = 'Epubeh829!';

let accessToken = null; // JWT токен после логина
let refreshToken = null; // Refresh token после логина
let userScopes = []; // Scopes пользователя из токена
let createdApiKey = null; // Созданный API ключ

// Функция для анализа структуры ответа с токеном
function analyzeTokenResponse(data, response, source) {
  if (response.status === 200 && data.token) {
    console.log(`\n✅ Успешно получен токен из ${source}!`);
    console.log('\nПроверка наличия полей:');
    console.log('- token:', !!data.token);
    console.log('- refresh_token:', !!data.refresh_token);
    console.log('- user:', !!data.user);
    console.log('- tenant:', !!data.tenant);
    
    // Декодируем JWT для просмотра payload
    const parts = data.token.split('.');
    if (parts.length === 3) {
      try {
        const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString());
        console.log('\nJWT Payload:');
        console.log('- sub (user_id):', payload.sub);
        console.log('- tenant_id:', payload.tenant_id);
        console.log('- scopes:', payload.scopes);
        console.log('- iss (issuer):', payload.iss);
        console.log('- aud (audience):', payload.aud);
        
        // Проверяем наличие exp и iat
        if (payload.exp) {
          console.log('- exp (expiration):', new Date(payload.exp * 1000).toISOString());
          
          // Проверяем время жизни токена
          const expiresIn = payload.exp * 1000 - Date.now();
          const expiresInMinutes = Math.floor(expiresIn / 60000);
          console.log('- expires_in:', `${expiresInMinutes} минут`);
        } else {
          console.log('- exp (expiration): отсутствует (токен без срока действия)');
        }
        
        if (payload.iat) {
          console.log('- iat (issued at):', new Date(payload.iat * 1000).toISOString());
        } else {
          console.log('- iat (issued at): отсутствует');
        }
        
        if (payload.jti) {
          console.log('- jti (JWT ID):', payload.jti);
        }
      } catch (e) {
        console.log('\n⚠️  Не удалось декодировать JWT payload:', e.message);
      }
    }
    
    // Важно: проверяем наличие refresh_token
    if (data.refresh_token) {
      console.log('\n✅ Refresh token присутствует в ответе!');
      console.log('   Фронтенд готов использовать refresh token для автоматического обновления сессии.');
      return true;
    } else {
      console.log('\n⚠️  Refresh token отсутствует в ответе.');
      console.log('   Нужно добавить поддержку refresh token на бэкенде.');
      console.log('   Без refresh token сессия будет прерываться каждые 15 минут.');
      return false;
    }
  } else {
    console.log(`\n❌ Ошибка получения токена из ${source}`);
    if (data.detail) {
      console.log('Error:', data.detail.error);
      console.log('Message:', data.detail.message);
    }
    return false;
  }
}

async function createApiKey() {
  console.log('\n=== Создание API ключа ===\n');
  
  if (!accessToken) {
    console.log('❌ Нет access token. Сначала нужно войти через email/пароль.\n');
    return null;
  }
  
  // Используем scopes пользователя или минимальный набор
  const scopesToUse = userScopes.length > 0 ? userScopes : ['tools:read', 'tools:write'];
  console.log(`Используемые scopes: ${scopesToUse.join(', ')}`);
  
  try {
    const response = await fetch(`${API_BASE}/api-keys`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      body: JSON.stringify({
        scopes: scopesToUse
      })
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('❌ Ошибка парсинга JSON ответа:', e.message);
      console.log('Raw response:', await response.text());
      return null;
    }
    
    console.log('Status:', response.status);
    console.log('Response structure:');
    console.log(JSON.stringify(data, null, 2));
    
    if (response.status === 200 || response.status === 201) {
      console.log('\n✅ API ключ успешно создан!');
      // API ключ может быть в разных полях в зависимости от бэкенда
      const apiKey = data.api_key || data.key || data.key_value || data.id || data.token;
      if (apiKey) {
        console.log('API Key:', apiKey);
        return apiKey;
      } else {
        console.log('⚠️  API ключ не найден в ответе. Проверьте структуру ответа выше.');
        console.log('   Возможные поля: api_key, key, key_value, id, token');
        return null;
      }
    } else {
      console.log('\n❌ Ошибка создания API ключа');
      if (data.detail) {
        // data.detail может быть строкой или объектом
        if (typeof data.detail === 'string') {
          console.log('Error:', data.detail);
        } else {
          console.log('Error:', data.detail.error);
          console.log('Message:', data.detail.message);
        }
      } else if (data.error) {
        console.log('Error:', data.error);
        console.log('Message:', data.message);
      }
      
      if (response.status === 403) {
        console.log('\n💡 Подсказка:');
        console.log('   Возможно, вы пытаетесь создать ключ со scopes, которых нет у пользователя.');
        console.log(`   Доступные scopes пользователя: ${userScopes.join(', ') || 'не определены'}`);
        console.log('   Попробуйте использовать только доступные scopes.');
      }
      
      return null;
    }
    
  } catch (error) {
    console.error('❌ Ошибка сети:', error.message);
    if (error.code === 'ENOTFOUND') {
      console.error('   Не удается найти хост. Проверьте доступность API.');
    } else if (error.code === 'ECONNREFUSED') {
      console.error('   Соединение отклонено. Проверьте, что API сервер запущен.');
    }
    console.error('   Полная ошибка:', error);
    return null;
  }
}

async function testApiKeyAuth(apiKey) {
  console.log('\n=== Тест получения токена по API ключу ===\n');
  
  if (!apiKey) {
    console.log('❌ API ключ не предоставлен. Пропускаем тест.\n');
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/auth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey
      },
      body: JSON.stringify({ api_key: apiKey })
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('❌ Ошибка парсинга JSON ответа:', e.message);
      console.log('Raw response:', text);
      return;
    }
    
    console.log('Status:', response.status);
    console.log('Response structure:');
    console.log(JSON.stringify(data, null, 2));
    
    analyzeTokenResponse(data, response, 'API ключа');
    
  } catch (error) {
    console.error('❌ Ошибка сети:', error.message);
    if (error.code === 'ENOTFOUND') {
      console.error('   Не удается найти хост. Проверьте доступность API.');
    } else if (error.code === 'ECONNREFUSED') {
      console.error('   Соединение отклонено. Проверьте, что API сервер запущен.');
    }
    console.error('   Полная ошибка:', error);
  }
}

async function testLogin() {
  console.log('\n=== Тест логина по email и паролю ===\n');
  
  if (!PASSWORD) {
    console.log('⚠️  Пароль не указан. Используйте: PASSWORD=your_password node test-auth-api.js\n');
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: EMAIL,
        password: PASSWORD
      })
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('❌ Ошибка парсинга JSON ответа:', e.message);
      console.log('Raw response:', text);
      return false;
    }
    
    console.log('Status:', response.status);
    console.log('Response structure:');
    console.log(JSON.stringify(data, null, 2));
    
    if (response.status === 200 && data.token) {
      // Сохраняем токены для дальнейшего использования
      accessToken = data.token;
      if (data.refresh_token) {
        refreshToken = data.refresh_token;
      }
      
      // Извлекаем scopes из JWT токена
      const parts = data.token.split('.');
      if (parts.length === 3) {
        try {
          const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString());
          userScopes = payload.scopes || [];
        } catch (e) {
          // Если не удалось декодировать, используем scopes из ответа
          userScopes = data.user?.scopes || [];
        }
      } else {
        userScopes = data.user?.scopes || [];
      }
      
      // Анализируем ответ (проверяет refresh_token и показывает детали)
      const hasRefreshToken = analyzeTokenResponse(data, response, 'логина');
      
      // Показываем информацию о пользователе, если есть
      if (data.user) {
        console.log('\nИнформация о пользователе:');
        console.log('- email:', data.user.email);
        console.log('- full_name:', data.user.full_name);
        console.log('- role:', data.user.role);
        console.log('- scopes:', data.user.scopes);
      }
      
      if (data.tenant) {
        console.log('\nИнформация о tenant:');
        console.log('- name:', data.tenant.name);
        console.log('- id:', data.tenant.id);
      }
      
      return hasRefreshToken;
    } else {
      console.log('\n❌ Ошибка входа');
      if (data.detail) {
        console.log('Error:', data.detail.error);
        console.log('Message:', data.detail.message);
      } else if (data.error) {
        console.log('Error:', data.error);
        console.log('Message:', data.message);
      }
      console.log('\nВозможные причины:');
      console.log('1. Неверный email или пароль');
      console.log('2. Аккаунт неактивен');
      console.log('3. Превышен rate limit');
      return false;
    }
    
  } catch (error) {
    console.error('❌ Ошибка сети:', error.message);
    if (error.code === 'ENOTFOUND') {
      console.error('   Не удается найти хост. Проверьте доступность API.');
    } else if (error.code === 'ECONNREFUSED') {
      console.error('   Соединение отклонено. Проверьте, что API сервер запущен.');
    } else if (error.message.includes('fetch')) {
      console.error('   Проблема с fetch. Убедитесь, что используете Node.js 18+ или установлен node-fetch.');
    }
    console.error('   Полная ошибка:', error);
    return false;
  }
}

async function testRefreshToken() {
  console.log('\n=== Тест обновления токена через refresh token ===\n');
  
  if (!refreshToken) {
    console.log('❌ Нет refresh token. Пропускаем тест.\n');
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('❌ Ошибка парсинга JSON ответа:', e.message);
      console.log('Raw response:', text);
      return;
    }
    
    console.log('Status:', response.status);
    console.log('Response structure:');
    console.log(JSON.stringify(data, null, 2));
    
    if (response.status === 200 && data.token) {
      console.log('\n✅ Токен успешно обновлен через refresh token!');
      
      // Обновляем токены
      accessToken = data.token;
      if (data.refresh_token) {
        refreshToken = data.refresh_token;
        console.log('✅ Получен новый refresh token');
      } else {
        console.log('⚠️  Новый refresh token не получен (используется старый)');
      }
      
      // Анализируем новый токен
      analyzeTokenResponse(data, response, 'refresh');
    } else {
      console.log('\n❌ Ошибка обновления токена');
      if (data.detail) {
        if (typeof data.detail === 'string') {
          console.log('Error:', data.detail);
        } else {
          console.log('Error:', data.detail.error);
          console.log('Message:', data.detail.message);
        }
      } else if (data.error) {
        console.log('Error:', data.error);
        console.log('Message:', data.message);
      }
    }
    
  } catch (error) {
    console.error('❌ Ошибка сети:', error.message);
    if (error.code === 'ENOTFOUND') {
      console.error('   Не удается найти хост. Проверьте доступность API.');
    } else if (error.code === 'ECONNREFUSED') {
      console.error('   Соединение отклонено. Проверьте, что API сервер запущен.');
    }
    console.error('   Полная ошибка:', error);
  }
}

// Запуск тестов
(async () => {
  console.log('='.repeat(60));
  console.log('ТЕСТИРОВАНИЕ АУТЕНТИФИКАЦИИ И REFRESH TOKEN');
  console.log('='.repeat(60));
  console.log(`Node.js версия: ${nodeVersion}`);
  console.log(`API Base URL: ${API_BASE}`);
  console.log(`Email: ${EMAIL}`);
  console.log('='.repeat(60));
  
  if (!PASSWORD) {
    console.log('\n❌ Пароль не указан!');
    console.log('\nИспользование:');
    console.log('  PASSWORD=your_password node test-auth-api.js');
    console.log('\nПример:');
    console.log('  PASSWORD=Epubeh829! node test-auth-api.js\n');
    process.exit(1);
  }
  
  // Шаг 1: Вход через email/пароль
  const hasRefreshToken = await testLogin();
  
  if (!accessToken) {
    console.log('\n❌ Не удалось получить токен. Дальнейшие тесты невозможны.\n');
    process.exit(1);
  }
  
  // Шаг 2: Создание API ключа
  createdApiKey = await createApiKey();
  
  // Шаг 3: Получение токена по API ключу (если ключ создан)
  if (createdApiKey) {
    await testApiKeyAuth(createdApiKey);
  }
  
  // Шаг 4: Тест обновления токена через refresh token (если есть)
  if (refreshToken) {
    await testRefreshToken();
  }
  
  // Итоговое резюме
  console.log('\n' + '='.repeat(60));
  console.log('ИТОГОВОЕ РЕЗЮМЕ');
  console.log('='.repeat(60));
  
  if (hasRefreshToken) {
    console.log('\n✅ Refresh token поддерживается на бэкенде!');
    console.log('   ✅ Фронтенд готов использовать refresh token для автоматического обновления сессии.');
    console.log('   ✅ Сессия не будет прерываться во время работы пользователя.');
    console.log('\n   Проверьте, что эндпоинт POST /auth/refresh работает корректно.');
  } else {
    console.log('\n⚠️  Refresh token НЕ поддерживается на бэкенде.');
    console.log('   Нужно добавить поддержку refresh token на бэкенде:');
    console.log('   1. Эндпоинт POST /auth/refresh');
    console.log('   2. Возврат refresh_token в ответах /auth/login, /auth/register, /auth/token');
    console.log('   3. Хранение refresh токенов в базе данных');
    console.log('\n   Без refresh token сессия будет прерываться каждые 15 минут.');
  }
  
  if (createdApiKey) {
    console.log('\n✅ API ключ успешно создан и протестирован.');
    console.log('   API Key:', createdApiKey);
    console.log('   Сохраните этот ключ для дальнейшего использования.');
  }
  
  console.log('\n');
})();
