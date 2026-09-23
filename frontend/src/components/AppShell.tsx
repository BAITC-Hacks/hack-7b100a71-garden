import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { copy } from '../i18n/en'
import { apiMode } from '../services/api'
import { EmployeeSelector } from './EmployeeSelector'
import { Icon } from './Icon'
import { ApiSessionControls } from './ApiAccess'

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const workspaceTitle = pathname === '/hr/dataset' ? copy.dataset.nav : pathname === '/hr' ? copy.hrNav : copy.employeeNav
  const main = useRef<HTMLElement>(null)
  const navigation = useRef<HTMLElement>(null)
  const menuButton = useRef<HTMLButtonElement>(null)
  const previousPath = useRef(pathname)
  function closeNavigation() {
    setMenuOpen(false)
    if (menuOpen) main.current?.focus()
  }
  useEffect(() => {
    if (menuOpen) navigation.current?.querySelector('a')?.focus()
  }, [menuOpen])
  useEffect(() => {
    if (previousPath.current !== pathname) {
      previousPath.current = pathname
      main.current?.focus()
      window.scrollTo({ top: 0, behavior: 'instant' })
    }
    document.title = `${workspaceTitle} · ${copy.brand}`
  }, [pathname, workspaceTitle])

  return <div className="app-shell" onKeyDown={(event) => {
    if (event.key === 'Escape' && menuOpen) {
      event.preventDefault()
      setMenuOpen(false)
      menuButton.current?.focus()
    }
  }}>
    <a className="skip-link" href="#main-content">{copy.skip}</a>
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <Link className="brand" to="/" onClick={closeNavigation}>
        <span className="brand-mark"><Icon name="compass" /></span>
        <span>Career<span className="brand-second">Quest<span className="brand-dot">.</span></span></span>
      </Link>
      <p className="nav-label">{copy.workspace}</p>
      <nav ref={navigation} aria-label={copy.workspace} id="workspace-navigation">
        <Link to="/" className={`nav-item ${pathname === '/' || pathname.startsWith('/employees/') ? 'active' : ''}`}
          aria-current={pathname === '/' || pathname.startsWith('/employees/') ? 'page' : undefined} onClick={closeNavigation}>
          <Icon name="grid" />{copy.employeeNav}
        </Link>
        <NavLink to="/hr" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeNavigation}>
          <Icon name="chart" />{copy.hrNav}
        </NavLink>
      </nav>
      <div className="sidebar-message"><Icon name="spark" /><p>{copy.tagline}</p><span>{copy.footerDetail}</span></div>
      <div className="sidebar-bottom"><span className="status-dot" /><span>{apiMode === 'mock' ? copy.demo : apiMode === 'real' ? copy.liveWorkspace : copy.liveUnavailable}</span></div>
    </aside>
    <div className="workspace-content">
      <header className="topbar">
        <button ref={menuButton} className="menu-toggle" type="button" aria-label={copy.menu} aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? 'close' : 'menu'} /></button>
        <div className="breadcrumb"><span>{copy.breadcrumb}</span><Icon name="chevron" /><strong>{workspaceTitle}</strong></div>
        <div className="topbar-actions"><ApiSessionControls /><span className="demo-badge"><span className="status-dot" />{apiMode === 'mock' ? copy.demo : apiMode === 'real' ? copy.liveWorkspace : copy.liveUnavailable}</span><EmployeeSelector /></div>
      </header>
      <main className="main-content" id="main-content" ref={main} tabIndex={-1}><Outlet /></main>
      <footer className="footer"><span>{copy.footer}</span><span>{copy.brand} <span aria-hidden="true">↗</span></span></footer>
    </div>
  </div>
}
