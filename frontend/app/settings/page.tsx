export default function SettingsPage() {
  const groups = [
    {
      title: "Groq AI",
      description: "Language model for all content generation",
      fields: [
        { key: "GROQ_API_KEY",  label: "API Key",    hint: "sk-..." },
        { key: "GROQ_MODEL",    label: "Model",      hint: "llama-3.3-70b-versatile" },
      ],
    },
    {
      title: "LinkedIn",
      description: "Publishing and analytics access",
      fields: [
        { key: "LINKEDIN_ACCESS_TOKEN",   label: "Access Token",   hint: "Bearer token from OAuth" },
        { key: "LINKEDIN_ORG_URN",        label: "Org URN",        hint: "urn:li:organization:..." },
        { key: "LINKEDIN_PERSON_URN",     label: "Person URN",     hint: "urn:li:person:..." },
        { key: "LINKEDIN_CLIENT_ID",      label: "Client ID",      hint: "OAuth app client ID" },
        { key: "LINKEDIN_CLIENT_SECRET",  label: "Client Secret",  hint: "OAuth app secret" },
      ],
    },
    {
      title: "Website",
      description: "Blog publishing destination",
      fields: [
        { key: "WEBSITE_REPO_PATH",  label: "Repo Path",   hint: "C:\\Projects\\phoenixsolution" },
        { key: "WEBSITE_BASE_URL",   label: "Base URL",    hint: "https://www.phoenixsolution.in" },
      ],
    },
    {
      title: "Google Analytics",
      description: "Website traffic metrics (optional)",
      fields: [
        { key: "GA_PROPERTY_ID", label: "Property ID", hint: "Leave blank to skip GA collection" },
      ],
    },
    {
      title: "Image Generation",
      description: "Stable Diffusion for blog images",
      fields: [
        { key: "STABLE_DIFFUSION_URL",   label: "SD URL",         hint: "http://127.0.0.1:7860" },
        { key: "UNSPLASH_ACCESS_KEY",    label: "Unsplash Key",   hint: "Fallback image source" },
      ],
    },
  ];

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ letterSpacing: "-0.02em" }}>
          <span className="gradient-text">Settings</span>
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Environment variable reference — edit your <code className="px-1.5 py-0.5 rounded text-xs" style={{ background: "var(--surface-2)", color: "#ff6a3d" }}>.env</code> file to update values
        </p>
      </div>

      {/* Read-only notice */}
      <div
        className="flex items-start gap-3 px-4 py-3 rounded-xl mb-8 text-sm"
        style={{ background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.2)", color: "#facc15" }}
      >
        <span className="mt-0.5 flex-shrink-0">⚠️</span>
        <p>
          Settings are read from the <strong>.env</strong> file at project root. This page shows the expected keys — values are not displayed for security. Restart the API server after any changes.
        </p>
      </div>

      <div className="space-y-6">
        {groups.map(group => (
          <div key={group.title} className="card-glass p-6">
            <div className="mb-5">
              <h2 className="font-semibold text-base" style={{ color: "var(--text-primary)" }}>
                {group.title}
              </h2>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                {group.description}
              </p>
            </div>
            <div className="space-y-4">
              {group.fields.map(f => (
                <div key={f.key} className="flex items-start gap-4">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wider" style={{ color: "#475569" }}>
                      {f.label}
                    </label>
                    <div
                      className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm"
                      style={{
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid var(--border)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      <code className="text-xs font-mono" style={{ color: "#ff6a3d" }}>{f.key}</code>
                      <span className="text-xs" style={{ color: "#334155" }}>·</span>
                      <span className="text-xs">{f.hint}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Restart command */}
      <div className="card-glass p-6 mt-6">
        <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "#475569" }}>
          Start API Server
        </p>
        <code
          className="block text-xs p-4 rounded-xl leading-relaxed overflow-x-auto"
          style={{ background: "rgba(0,0,0,0.4)", color: "#94a3b8", border: "1px solid var(--border)" }}
        >
          {`"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000`}
        </code>
        <p className="text-xs mt-3" style={{ color: "#475569" }}>
          Run from: <code style={{ color: "#ff6a3d" }}>d:\Projects\BlogMarketing\</code>
        </p>
      </div>
    </div>
  );
}
