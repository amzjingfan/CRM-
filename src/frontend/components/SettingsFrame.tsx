import { AppShell } from "./AppShell";
import { SettingsNav } from "./SettingsNav";

export function SettingsFrame({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <AppShell><main className="management-page settings-page">
    <div className="settings-layout">
      <SettingsNav />
      <div className="settings-main">
        <header className="settings-page-header"><div><p className="eyebrow">SYSTEM SETTINGS</p><h1>{title}</h1><p>{description}</p></div></header>
        {children}
      </div>
    </div>
  </main></AppShell>;
}
