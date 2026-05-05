---
description: Запустить полный деплой через infra/scripts/deploy.sh full
allowed-tools: Bash
---

Запусти полный деплой и покажи итоговый статус контейнеров.

```bash
export SUDO_ASKPASS=/opt/myapp/.claude/sudo-askpass.sh && cd /opt/myapp/infra && ./scripts/deploy.sh full $ARGUMENTS
```

После завершения:
- Если есть упавшие контейнеры — собери логи последних 50 строк по каждому и кратко резюмируй причину.
- Если всё OK — выведи короткое подтверждение и URL мониторинга из вывода скрипта.
