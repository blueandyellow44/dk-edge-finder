type HeaderProps = {
  email: string | undefined
  pictureUrl: string | null
}

export function Header({ email, pictureUrl }: HeaderProps) {
  const initial = email ? email[0].toUpperCase() : '?'
  return (
    <header className="header">
      <div className="header-logo">
        DK <span className="gold">EDGE</span>
        <span className="tag">FINDER</span>
      </div>
      <div className="header-right">
        <div className="header-account">
          <span className="header-avatar" aria-hidden="true">
            {pictureUrl ? <img src={pictureUrl} alt="" /> : initial}
          </span>
          <span>{email ?? '...'}</span>
        </div>
        <a className="header-link" href="/cdn-cgi/access/logout">
          Sign out
        </a>
      </div>
    </header>
  )
}
