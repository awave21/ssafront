#!/usr/bin/env python3
"""
Тестовый клиент для WebSocket API.

Использование:
    python scripts/test_websocket.py --token JWT_TOKEN --agent-id AGENT_UUID

Пример:
    python scripts/test_websocket.py \
        --token eyJhbGciOiJIUzI1NiIs... \
        --agent-id 12345678-1234-1234-1234-123456789abc \
        --url ws://localhost:8000/api/v1
"""
import argparse
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Установите websockets: pip install websockets")
    sys.exit(1)


async def test_websocket(url: str, agent_id: str, token: str):
    """Тестирование WebSocket соединения."""
    ws_url = f"{url}/agents/{agent_id}/ws?token={token}"
    print(f"Подключение к: {ws_url[:100]}...")
    
    try:
        async with websockets.connect(ws_url) as ws:
            print("✅ Подключено!")
            
            # Запускаем параллельные задачи
            receive_task = asyncio.create_task(receive_messages(ws))
            send_task = asyncio.create_task(send_commands(ws))
            
            await asyncio.gather(receive_task, send_task)
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Ошибка подключения: HTTP {e.status_code}")
        if e.status_code == 403:
            print("   Проверьте токен и доступ к агенту")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


async def receive_messages(ws):
    """Получение и вывод сообщений от сервера."""
    try:
        async for message in ws:
            data = json.loads(message)
            event_type = data.get("type", "unknown")
            
            if event_type == "ping":
                print("🏓 Ping получен")
                # Отвечаем pong
                await ws.send(json.dumps({"type": "pong"}))
            elif event_type == "message_created":
                msg_data = data.get("data", {})
                print(f"📨 Новое сообщение [{msg_data.get('role')}]: {msg_data.get('content', '')[:100]}")
            elif event_type == "dialog_updated":
                dialog = data.get("data", {})
                print(f"📋 Диалог обновлен: {dialog.get('title', 'N/A')}")
            elif event_type == "run_start":
                run_data = data.get("data", {})
                print(f"🚀 Запуск агента: run_id={run_data.get('run_id')}")
            elif event_type == "run_result":
                run_data = data.get("data", {})
                print(f"✅ Результат агента: {run_data.get('output', '')[:200]}")
            elif event_type == "run_error":
                err_data = data.get("data", {})
                print(f"❌ Ошибка агента: {err_data.get('error')}")
            elif event_type == "status":
                status = data.get("data", {})
                print(f"📊 Статус: connections={status.get('connections_count')}")
            elif event_type == "error":
                err = data.get("data", {})
                print(f"⚠️ Ошибка: {err.get('message')}")
            else:
                print(f"📬 {event_type}: {json.dumps(data.get('data', {}), ensure_ascii=False)[:200]}")
                
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Соединение закрыто")


async def send_commands(ws):
    """Интерактивная отправка команд."""
    print("\n📝 Команды:")
    print("  status - получить статус соединения")
    print("  join <dialog_id> - подписаться на диалог")
    print("  leave <dialog_id> - отписаться от диалога")
    print("  send <dialog_id> <message> - отправить сообщение")
    print("  quit - выйти\n")
    
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            # Читаем ввод в отдельном потоке, чтобы не блокировать event loop
            line = await loop.run_in_executor(None, input, "> ")
            line = line.strip()
            
            if not line:
                continue
            
            parts = line.split(maxsplit=2)
            cmd = parts[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                print("👋 Выход...")
                break
            
            elif cmd == "status":
                await ws.send(json.dumps({"type": "get_status"}))
            
            elif cmd == "join" and len(parts) >= 2:
                dialog_id = parts[1]
                await ws.send(json.dumps({
                    "type": "join_dialog",
                    "dialog_id": dialog_id
                }))
                print(f"📥 Подписка на диалог: {dialog_id}")
            
            elif cmd == "leave" and len(parts) >= 2:
                dialog_id = parts[1]
                await ws.send(json.dumps({
                    "type": "leave_dialog",
                    "dialog_id": dialog_id
                }))
                print(f"📤 Отписка от диалога: {dialog_id}")
            
            elif cmd == "send" and len(parts) >= 3:
                dialog_id = parts[1]
                message = parts[2]
                await ws.send(json.dumps({
                    "type": "send_message",
                    "dialog_id": dialog_id,
                    "content": message
                }))
                print(f"📤 Отправлено в {dialog_id}: {message}")
            
            else:
                print("❓ Неизвестная команда. Используйте: status, join, leave, send, quit")
                
        except EOFError:
            break
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")


def main():
    parser = argparse.ArgumentParser(description="Тестовый клиент WebSocket API")
    parser.add_argument("--url", default="ws://localhost:8000/api/v1",
                        help="WebSocket URL (по умолчанию: ws://localhost:8000/api/v1)")
    parser.add_argument("--agent-id", required=True, help="UUID агента")
    parser.add_argument("--token", required=True, help="JWT токен")
    
    args = parser.parse_args()
    
    asyncio.run(test_websocket(args.url, args.agent_id, args.token))


if __name__ == "__main__":
    main()
