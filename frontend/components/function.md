<div
  class="export-wrapper"
  style="
    width: 1440px;
    min-height: 812px;
    position: relative;
    font-family: var(--font-family-body);
    background-color: var(--background);
  "
>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@100;200;300;400;500;600;700;800;900&family=Geist:wght@100;200;300;400;500;600;700;800;900&family=IBM+Plex+Mono:wght@100;200;300;400;500;600;700&family=IBM+Plex+Sans:wght@100;200;300;400;500;600;700&family=Inter:wght@100;200;300;400;500;600;700;800;900&family=Nunito:wght@200;300;400;500;600;700;800;900&family=PT+Serif:wght@400;700&family=Roboto+Slab:wght@100;200;300;400;500;600;700;800;900&family=Roboto:wght@100;300;400;500;700;900&family=Shantell+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@300;400;500;600;700&display=swap"
    rel="stylesheet"
  />
  <html>
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>Agent Functions - POST Editor</title>
      <style>
        * {
          box-sizing: border-box;
          outline: none;
        }
        .export-wrapper {
          margin: 0;
          padding: 0;
          min-height: 812px;
          display: flex;
          background-color: var(--background);
          color: var(--foreground);
          font-family: var(
            --font-family-body,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Roboto,
            Helvetica,
            Arial,
            sans-serif
          );
          -webkit-font-smoothing: antialiased;
        }

        :root {
          --background: #ffffff;
          --foreground: #0f172a;
          --muted: #f1f5f9;
          --muted-foreground: #64748b;
          --border: #e2e8f0;
          --input: #ffffff;
          --primary: #0f172a;
          --primary-foreground: #ffffff;
          --secondary: #f1f5f9;
          --secondary-foreground: #0f172a;
          --accent: #f1f5f9;
          --accent-foreground: #0f172a;
          --destructive: #ef4444;
          --destructive-foreground: #f8fafc;
          --radius-md: 6px;
          --radius-lg: 8px;
          --radius-sm: 4px;
          --sidebar: #f8fafc;
          --sidebar-foreground: #64748b;
          --sidebar-primary: #e2e8f0;
          --sidebar-primary-foreground: #0f172a;
          --card: #ffffff;
          --success: #10b981;
        }

        .app-container {
          display: flex;
          width: 100%;
          height: 100vh;
          overflow: hidden;
        }

        /* Sidebar */
        .sidebar {
          width: 64px;
          background-color: var(--sidebar);
          border-right: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 16px 0;
          flex-shrink: 0;
          z-index: 20;
        }
        .logo {
          width: 36px;
          height: 36px;
          background-color: var(--primary);
          border-radius: var(--radius-md);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--primary-foreground);
          font-weight: 700;
          font-size: 18px;
          margin-bottom: 32px;
          cursor: pointer;
        }
        .nav-icon {
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 8px;
          border-radius: var(--radius-md);
          color: var(--sidebar-foreground);
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .nav-icon:hover {
          background-color: var(--sidebar-primary);
          color: var(--sidebar-primary-foreground);
        }
        .nav-icon.active {
          background-color: var(--sidebar-primary);
          color: var(--sidebar-primary-foreground);
        }
        .spacer {
          flex: 1;
        }
        .user-avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background-color: var(--muted);
          margin-top: 16px;
          overflow: hidden;
          cursor: pointer;
        }
        .user-avatar img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        /* Main Layout */
        .main-area {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .top-bar {
          height: 60px;
          border-bottom: 1px solid var(--border);
          background-color: var(--background);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 24px;
          flex-shrink: 0;
        }
        .breadcrumbs {
          font-size: 13px;
          color: var(--muted-foreground);
          display: flex;
          align-items: center;
          gap: 8px;
          font-weight: 500;
        }
        .breadcrumbs span.active {
          color: var(--foreground);
        }
        .top-actions {
          display: flex;
          gap: 12px;
        }

        .workspace-grid {
          display: flex;
          flex: 1;
          overflow: hidden;
          background-color: var(--muted);
        }

        /* List Column */
        .col-list {
          width: 280px;
          background-color: var(--background);
          border-right: 1px solid var(--border);
          display: flex;
          flex-direction: column;
        }
        .list-header {
          padding: 16px;
          border-bottom: 1px solid var(--border);
        }
        .search-box {
          position: relative;
          margin-top: 12px;
        }
        .search-box iconify-icon {
          position: absolute;
          left: 10px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--muted-foreground);
        }
        .search-input {
          width: 100%;
          padding: 8px 10px 8px 32px;
          border-radius: var(--radius-md);
          border: 1px solid var(--border);
          background-color: var(--input);
          font-size: 13px;
          color: var(--foreground);
        }
        .func-list {
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }
        .func-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: background 0.1s;
          margin-bottom: 2px;
          border: 1px solid transparent;
        }
        .func-item:hover {
          background-color: var(--muted);
        }
        .func-item.active {
          background-color: #f1f5f9;
          border-color: var(--border);
        }
        .method-badge {
          font-size: 9px;
          font-weight: 700;
          padding: 3px 6px;
          border-radius: 4px;
          min-width: 38px;
          text-align: center;
          text-transform: uppercase;
        }
        .method-get {
          color: #059669;
          background: #d1fae5;
        }
        .method-post {
          color: #2563eb;
          background: #dbeafe;
        }
        .method-put {
          color: #d97706;
          background: #fef3c7;
        }
        .method-del {
          color: #dc2626;
          background: #fee2e2;
        }
        .func-info {
          flex: 1;
          overflow: hidden;
        }
        .func-name {
          font-size: 13px;
          font-weight: 500;
          color: var(--foreground);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .func-meta {
          font-size: 11px;
          color: var(--muted-foreground);
        }
        .status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background-color: var(--success);
          flex-shrink: 0;
        }

        /* Editor Column */
        .col-editor {
          flex: 1;
          background-color: var(--background);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-width: 460px;
        }
        .editor-header {
          padding: 24px 32px;
          border-bottom: 1px solid var(--border);
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          background-color: var(--background);
        }
        .editor-title-area h2 {
          margin: 0;
          font-size: 20px;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .id-pill {
          font-size: 11px;
          font-family: monospace;
          background-color: var(--muted);
          padding: 2px 6px;
          border-radius: 4px;
          color: var(--muted-foreground);
          font-weight: 400;
        }
        .editor-scroll {
          flex: 1;
          overflow-y: auto;
          padding: 32px;
        }
        .section-title {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 16px;
          color: var(--foreground);
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .section-card {
          background-color: var(--card);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: 24px;
          margin-bottom: 32px;
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }

        /* Form Elements */
        .label {
          display: block;
          font-size: 12px;
          font-weight: 500;
          margin-bottom: 6px;
          color: var(--foreground);
        }
        .url-bar {
          display: flex;
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          overflow: hidden;
          background: var(--input);
        }
        .method-select {
          width: 100px;
          background-color: var(--muted);
          border: none;
          border-right: 1px solid var(--border);
          padding: 0 12px;
          font-size: 13px;
          font-weight: 600;
          color: var(--foreground);
          cursor: pointer;
          appearance: none;
          outline: none;
        }
        .url-input {
          flex: 1;
          border: none;
          padding: 10px 12px;
          font-size: 13px;
          font-family: monospace;
          color: var(--foreground);
          outline: none;
        }

        .config-tabs {
          display: flex;
          gap: 24px;
          border-bottom: 1px solid var(--border);
          margin-bottom: 24px;
        }
        .config-tab {
          padding-bottom: 10px;
          font-size: 13px;
          font-weight: 500;
          color: var(--muted-foreground);
          cursor: pointer;
          position: relative;
        }
        .config-tab.active {
          color: var(--foreground);
        }
        .config-tab.active::after {
          content: "";
          position: absolute;
          bottom: -1px;
          left: 0;
          width: 100%;
          height: 2px;
          background-color: var(--primary);
        }

        /* Fields Table specific */
        .fields-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }
        .view-toggle {
          display: flex;
          background: var(--muted);
          border-radius: var(--radius-md);
          padding: 3px;
          gap: 2px;
        }
        .view-toggle-btn {
          padding: 4px 12px;
          font-size: 12px;
          border-radius: 4px;
          cursor: pointer;
          color: var(--muted-foreground);
          font-weight: 500;
        }
        .view-toggle-btn.active {
          background: var(--background);
          color: var(--foreground);
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }

        .fields-table {
          width: 100%;
          border-collapse: separate;
          border-spacing: 0;
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          overflow: hidden;
        }
        .fields-table th {
          background-color: var(--muted);
          text-align: left;
          font-weight: 600;
          color: var(--muted-foreground);
          padding: 10px 12px;
          font-size: 11px;
          border-bottom: 1px solid var(--border);
          text-transform: uppercase;
        }
        .fields-table td {
          padding: 8px 12px;
          border-bottom: 1px solid var(--border);
          background: var(--background);
          vertical-align: middle;
        }
        .fields-table tr:last-child td {
          border-bottom: none;
        }
        .table-input {
          width: 100%;
          border: 1px solid transparent;
          padding: 6px 8px;
          border-radius: 4px;
          font-size: 13px;
          background: transparent;
          color: var(--foreground);
        }
        .table-input:hover {
          background: var(--muted);
        }
        .table-input:focus {
          background: var(--background);
          border-color: var(--primary);
          box-shadow: 0 0 0 1px var(--primary);
        }
        .type-select {
          border: none;
          background: transparent;
          font-size: 12px;
          color: var(--muted-foreground);
          cursor: pointer;
          width: 100%;
          font-weight: 500;
        }

        /* Tools Column */
        .col-tools {
          width: 360px;
          background-color: var(--card);
          border-left: 1px solid var(--border);
          display: flex;
          flex-direction: column;
        }
        .tools-header {
          height: 48px;
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px;
          background-color: var(--muted);
          font-size: 12px;
          font-weight: 600;
          color: var(--muted-foreground);
          text-transform: uppercase;
        }
        .schema-editor {
          flex: 1;
          background-color: var(--background);
          padding: 16px;
          font-family: Menlo, "Courier New", monospace;
          font-size: 12px;
          line-height: 1.6;
          overflow-y: auto;
          border-bottom: 1px solid var(--border);
        }
        .key {
          color: #7c3aed;
        }
        .string {
          color: #059669;
        }
        .number {
          color: #d97706;
        }

        .test-console {
          height: 40%;
          display: flex;
          flex-direction: column;
          background-color: var(--background);
        }
        .console-toolbar {
          padding: 8px 16px;
          background-color: var(--muted);
          border-bottom: 1px solid var(--border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .btn-run {
          background-color: var(--primary);
          color: var(--primary-foreground);
          border: none;
          border-radius: var(--radius-sm);
          padding: 4px 12px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        /* Common Buttons */
        .btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: var(--radius-md);
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          height: 32px;
          padding: 0 12px;
          transition: all 0.2s;
          border: 1px solid transparent;
        }
        .btn-outline {
          border-color: var(--border);
          background-color: transparent;
          color: var(--foreground);
        }
        .btn-outline:hover {
          background-color: var(--muted);
        }
        .btn-ghost {
          background-color: transparent;
          color: var(--muted-foreground);
          height: auto;
          padding: 4px 8px;
        }
        .btn-ghost:hover {
          background-color: var(--muted);
          color: var(--foreground);
        }
        .btn-add {
          margin-top: 12px;
          color: var(--primary);
          font-size: 13px;
          background: none;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 0;
        }
        .btn-add:hover {
          text-decoration: underline;
        }

        /* Switch */
        .switch {
          position: relative;
          display: inline-block;
          width: 36px;
          height: 20px;
        }
        .switch input {
          opacity: 0;
          width: 0;
          height: 0;
        }
        .slider {
          position: absolute;
          cursor: pointer;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: var(--border);
          transition: 0.2s;
          border-radius: 34px;
        }
        .slider:before {
          position: absolute;
          content: "";
          height: 16px;
          width: 16px;
          left: 2px;
          bottom: 2px;
          background-color: white;
          transition: 0.2s;
          border-radius: 50%;
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }
        input:checked + .slider {
          background-color: var(--primary);
        }
        input:checked + .slider:before {
          transform: translateX(16px);
        }
      </style>
    </head>
    <body>
      <div class="app-container">
        <!-- Sidebar -->
        <aside class="sidebar">
          <div class="logo" data-media-type="banani-button">B</div>
          <div class="nav-icon" data-media-type="banani-button">
            <iconify-icon
              icon="lucide:layout-grid"
              style="font-size: 20px"
            ></iconify-icon>
          </div>
          <div class="nav-icon active" data-media-type="banani-button">
            <iconify-icon
              icon="lucide:bot"
              style="font-size: 20px"
            ></iconify-icon>
          </div>
          <div class="nav-icon" data-media-type="banani-button">
            <iconify-icon
              icon="lucide:message-square"
              style="font-size: 20px"
            ></iconify-icon>
          </div>
          <div class="nav-icon" data-media-type="banani-button">
            <iconify-icon
              icon="lucide:bar-chart-2"
              style="font-size: 20px"
            ></iconify-icon>
          </div>
          <div class="spacer"></div>
          <div class="nav-icon" data-media-type="banani-button">
            <iconify-icon
              icon="lucide:settings"
              style="font-size: 20px"
            ></iconify-icon>
          </div>
          <div class="user-avatar" data-media-type="banani-button">
            <img
              src="https://storage.googleapis.com/banani-avatars/avatar%2Ffemale%2F25-35%2FEuropean%2F3"
              alt="User"
            />
          </div>
        </aside>

        <!-- Main Content -->
        <div class="main-area">
          <header class="top-bar">
            <div class="breadcrumbs">
              <span>Агенты</span>
              <iconify-icon
                icon="lucide:chevron-right"
                style="font-size: 14px"
              ></iconify-icon>
              <span>Саппорт Бот</span>
              <iconify-icon
                icon="lucide:chevron-right"
                style="font-size: 14px"
              ></iconify-icon>
              <span class="active">Функции</span>
            </div>
            <div class="top-actions">
              <button class="btn btn-outline" data-media-type="banani-button">
                <iconify-icon
                  icon="lucide:book"
                  style="font-size: 14px; margin-right: 6px"
                ></iconify-icon>
                Документация
              </button>
              <button
                class="btn"
                style="
                  background: var(--primary);
                  color: var(--primary-foreground);
                "
                data-media-type="banani-button"
              >
                Опубликовать
              </button>
            </div>
          </header>

          <div class="workspace-grid">
            <!-- Left: Function List -->
            <div class="col-list">
              <div class="list-header">
                <div
                  style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                  "
                >
                  <span style="font-weight: 600; font-size: 14px">Функции</span>
                  <button class="btn-ghost" data-media-type="banani-button">
                    <iconify-icon
                      icon="lucide:plus"
                      style="font-size: 16px; color: var(--primary)"
                    ></iconify-icon>
                  </button>
                </div>
                <div class="search-box">
                  <iconify-icon icon="lucide:search"></iconify-icon>
                  <input
                    type="text"
                    class="search-input"
                    placeholder="Filter..."
                  />
                </div>
              </div>
              <div class="func-list">
                <div class="func-item" data-media-type="banani-button">
                  <span class="method-badge method-get">GET</span>
                  <div class="func-info">
                    <div class="func-name">check_availability</div>
                    <div class="func-meta">crm, booking</div>
                  </div>
                  <div class="status-dot"></div>
                </div>

                <div class="func-item active" data-media-type="banani-button">
                  <span class="method-badge method-post">POST</span>
                  <div class="func-info">
                    <div class="func-name">create_appointment</div>
                    <div class="func-meta">prod, crm</div>
                  </div>
                  <div class="status-dot"></div>
                </div>

                <div class="func-item" data-media-type="banani-button">
                  <span class="method-badge method-put">PUT</span>
                  <div class="func-info">
                    <div class="func-name">update_client</div>
                    <div class="func-meta">crm</div>
                  </div>
                  <div
                    class="status-dot"
                    style="background-color: var(--border)"
                  ></div>
                </div>

                <div class="func-item" data-media-type="banani-button">
                  <span
                    class="method-badge"
                    style="background: #e5e7eb; color: #6b7280"
                    >LOC</span
                  >
                  <div class="func-info">
                    <div class="func-name">calc_delivery</div>
                    <div class="func-meta">utils</div>
                  </div>
                  <div class="status-dot"></div>
                </div>
              </div>
            </div>

            <!-- Center: Editor -->
            <div class="col-editor">
              <div class="editor-header">
                <div class="editor-title-area">
                  <h2>
                    create_appointment
                    <span class="id-pill">ID: func_post_09</span>
                  </h2>
                  <div
                    style="
                      margin-top: 6px;
                      color: var(--muted-foreground);
                      font-size: 13px;
                    "
                  >
                    Создание новой записи на прием через CRM API
                  </div>
                </div>
                <div style="display: flex; align-items: center; gap: 16px">
                  <div
                    style="
                      display: flex;
                      align-items: center;
                      gap: 8px;
                      font-size: 13px;
                      font-weight: 500;
                    "
                  >
                    <span>Active</span>
                    <label class="switch">
                      <input type="checkbox" checked="" />
                      <span class="slider"></span>
                    </label>
                  </div>
                  <button
                    class="btn-ghost"
                    style="color: var(--destructive)"
                    data-media-type="banani-button"
                  >
                    <iconify-icon
                      icon="lucide:trash-2"
                      style="font-size: 16px"
                    ></iconify-icon>
                  </button>
                </div>
              </div>

              <div class="editor-scroll">
                <!-- Config Section -->
                <div class="section-card">
                  <div class="section-title">
                    <iconify-icon
                      icon="lucide:server"
                      style="color: var(--primary)"
                    ></iconify-icon>
                    Endpoint Configuration
                  </div>

                  <div class="field-group" style="margin-bottom: 24px">
                    <label class="label">Request URL</label>
                    <div class="url-bar">
                      <select class="method-select">
                        <option>GET</option>
                        <option selected="">POST</option>
                        <option>PUT</option>
                        <option>DELETE</option>
                      </select>
                      <input
                        type="text"
                        class="url-input"
                        value="https://api.crm.io/v2/appointments"
                      />
                    </div>
                  </div>

                  <!-- Tabs -->
                  <div class="config-tabs">
                    <div class="config-tab" data-media-type="banani-button">
                      Auth
                    </div>
                    <div
                      class="config-tab active"
                      data-media-type="banani-button"
                    >
                      Body
                    </div>
                    <div class="config-tab" data-media-type="banani-button">
                      Headers
                    </div>
                    <div class="config-tab" data-media-type="banani-button">
                      Settings
                    </div>
                  </div>

                  <!-- Body Editor Content -->
                  <div class="body-content">
                    <div class="fields-header">
                      <div
                        style="
                          font-size: 12px;
                          font-weight: 500;
                          color: var(--foreground);
                          display: flex;
                          align-items: center;
                          gap: 8px;
                        "
                      >
                        Content-Type:
                        <span
                          style="
                            background: var(--muted);
                            padding: 2px 6px;
                            border-radius: 4px;
                            font-family: monospace;
                          "
                          >application/json</span
                        >
                      </div>
                      <div class="view-toggle">
                        <div
                          class="view-toggle-btn active"
                          data-media-type="banani-button"
                        >
                          Fields
                        </div>
                        <div
                          class="view-toggle-btn"
                          data-media-type="banani-button"
                        >
                          JSON
                        </div>
                      </div>
                    </div>

                    <table class="fields-table">
                      <thead>
                        <tr>
                          <th width="30%">Key</th>
                          <th width="20%">Type</th>
                          <th>Value</th>
                          <th width="36px"></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="doctor_id"
                            />
                          </td>
                          <td>
                            <select class="type-select">
                              <option>String</option>
                              <option selected="">Integer</option>
                              <option>Boolean</option>
                              <option>Array</option>
                              <option>Object</option>
                            </select>
                          </td>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="{{doctor_id}}"
                              style="
                                color: var(--primary);
                                font-family: monospace;
                                font-weight: 500;
                              "
                            />
                          </td>
                          <td>
                            <div
                              style="
                                display: flex;
                                justify-content: center;
                                cursor: pointer;
                                color: var(--muted-foreground);
                              "
                            >
                              <iconify-icon
                                icon="lucide:x"
                                style="font-size: 14px"
                              ></iconify-icon>
                            </div>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="client_name"
                            />
                          </td>
                          <td>
                            <select class="type-select">
                              <option selected="">String</option>
                              <option>Integer</option>
                            </select>
                          </td>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="{{user_name}}"
                              style="
                                color: var(--primary);
                                font-family: monospace;
                                font-weight: 500;
                              "
                            />
                          </td>
                          <td>
                            <div
                              style="
                                display: flex;
                                justify-content: center;
                                cursor: pointer;
                                color: var(--muted-foreground);
                              "
                            >
                              <iconify-icon
                                icon="lucide:x"
                                style="font-size: 14px"
                              ></iconify-icon>
                            </div>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="start_time"
                            />
                          </td>
                          <td>
                            <select class="type-select">
                              <option selected="">String</option>
                            </select>
                          </td>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="{{iso_date}}"
                              style="
                                color: var(--primary);
                                font-family: monospace;
                                font-weight: 500;
                              "
                            />
                          </td>
                          <td>
                            <div
                              style="
                                display: flex;
                                justify-content: center;
                                cursor: pointer;
                                color: var(--muted-foreground);
                              "
                            >
                              <iconify-icon
                                icon="lucide:x"
                                style="font-size: 14px"
                              ></iconify-icon>
                            </div>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="notify"
                            />
                          </td>
                          <td>
                            <select class="type-select">
                              <option>String</option>
                              <option selected="">Boolean</option>
                            </select>
                          </td>
                          <td>
                            <input
                              type="text"
                              class="table-input"
                              value="true"
                              style="
                                color: #059669;
                                font-family: monospace;
                                font-weight: 500;
                              "
                            />
                          </td>
                          <td>
                            <div
                              style="
                                display: flex;
                                justify-content: center;
                                cursor: pointer;
                                color: var(--muted-foreground);
                              "
                            >
                              <iconify-icon
                                icon="lucide:x"
                                style="font-size: 14px"
                              ></iconify-icon>
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <button class="btn-add" data-media-type="banani-button">
                      <iconify-icon
                        icon="lucide:plus-circle"
                        style="font-size: 14px"
                      ></iconify-icon>
                      Add new field
                    </button>
                  </div>
                </div>

                <!-- Instructions Section (Lower Priority visually) -->
                <div class="section-card">
                  <div class="section-title">
                    <iconify-icon
                      icon="lucide:brain-circuit"
                      style="color: var(--primary)"
                    ></iconify-icon>
                    AI Instructions
                  </div>
                  <div
                    style="
                      font-size: 13px;
                      color: var(--muted-foreground);
                      margin-bottom: 12px;
                    "
                  >
                    Specify when and how the AI should use this function.
                  </div>
                  <textarea
                    class="table-input"
                    style="
                      width: 100%;
                      border: 1px solid var(--border);
                      min-height: 80px;
                      resize: vertical;
                      line-height: 1.5;
                    "
                  >
Use this function when the user explicitly confirms the appointment details. Ensure doctor_id and time are available.</textarea
                  >
                </div>
              </div>
            </div>

            <!-- Right: Tools -->
            <div class="col-tools">
              <!-- Schema -->
              <div class="tools-header">
                <span>Input Schema (Generated)</span>
                <button
                  class="btn-ghost"
                  style="font-size: 11px"
                  data-media-type="banani-button"
                >
                  <iconify-icon
                    icon="lucide:refresh-cw"
                    style="font-size: 12px; margin-right: 4px"
                  ></iconify-icon>
                  Regenerate
                </button>
              </div>
              <div class="schema-editor">
                <span class="key">{</span>
                <span class="key">"type"</span>:
                <span class="string">"object"</span>,
                <span class="key">"properties"</span>:
                <span class="key">{</span> <span class="key">"doctor_id"</span>:
                <span class="key">{</span> <span class="key">"type"</span>:
                <span class="string">"integer"</span>
                <span class="key">}</span>,
                <span class="key">"client_name"</span>:
                <span class="key">{</span> <span class="key">"type"</span>:
                <span class="string">"string"</span> <span class="key">}</span>,
                <span class="key">"start_time"</span>:
                <span class="key">{</span> <span class="key">"type"</span>:
                <span class="string">"string"</span>
                <span class="key">}</span>
                <span class="key">}</span>, <span class="key">"required"</span>:
                [<span class="string">"doctor_id"</span>,
                <span class="string">"start_time"</span>]
                <span class="key">}</span>
              </div>

              <!-- Test Console -->
              <div
                class="tools-header"
                style="border-top: 1px solid var(--border)"
              >
                <span>Test Console</span>
              </div>
              <div class="test-console">
                <div class="console-toolbar">
                  <div style="font-size: 11px; font-weight: 500">
                    Payload Preview
                  </div>
                  <button class="btn-run" data-media-type="banani-button">
                    <iconify-icon
                      icon="lucide:play"
                      style="font-size: 12px"
                    ></iconify-icon>
                    Run Request
                  </button>
                </div>
                <div
                  style="
                    padding: 12px;
                    border-bottom: 1px solid var(--border);
                    flex: 1;
                  "
                >
                  <textarea
                    class="table-input"
                    style="
                      width: 100%;
                      height: 100%;
                      border: none;
                      resize: none;
                      font-family: monospace;
                      font-size: 12px;
                      color: var(--foreground);
                      padding: 0;
                    "
                  >
{
  "doctor_id": 101,
  "client_name": "Alex Doe",
  "start_time": "2024-10-25T14:30:00Z",
  "notify": true
}</textarea
                  >
                </div>
                <div
                  style="
                    padding: 8px 16px;
                    font-size: 11px;
                    color: var(--muted-foreground);
                    background: var(--muted);
                  "
                >
                  Status:
                  <span style="color: var(--foreground); font-weight: 600"
                    >Ready</span
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </body>
  </html>
  <script src="https://code.iconify.design/iconify-icon/3.0.0/iconify-icon.min.js"></script>
  <style>
    :root {
      --background: #f6f7fb;
      --foreground: #0f1724;
      --border: #00000014;
      --input: #ffffff;
      --primary: #7a6cbf;
      --primary-foreground: #ffffff;
      --secondary: #eef1ff;
      --secondary-foreground: #4b5563;
      --muted: #f2f4f7;
      --muted-foreground: #98a0b3;
      --success: #ecfdf3;
      --success-foreground: #047857;
      --accent: #7c5cff;
      --accent-foreground: #ffffff;
      --destructive: #fff1f2;
      --destructive-foreground: #c92a2a;
      --warning: #fffaeb;
      --warning-foreground: #b45309;
      --card: #ffffff;
      --card-foreground: #111827;
      --sidebar: #ffffff;
      --sidebar-foreground: #6b7280;
      --sidebar-primary: #5b3bff;
      --sidebar-primary-foreground: #ffffff;
      --radius-sm: 4px;
      --radius-md: 6px;
      --radius-lg: 8px;
      --radius-xl: 12px;
      --font-family-body: Inter;
    }
  </style>
</div>
