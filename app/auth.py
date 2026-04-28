import streamlit as st


def require_login() -> tuple[str, str]:
    """Gate the current page behind Google login. Returns (email, name).
    Logs the first access of the session automatically.
    """
    if not st.user.is_logged_in:
        col = st.columns([1, 2, 1])[1]
        with col:
            st.markdown("---")
            st.markdown("## Sistema de Gestão de Incidentes")
            st.info("Faça login com sua conta Google para acessar a plataforma.")
            st.login("google")
        st.stop()

    email = st.user.email
    name = st.user.name or email

    if not st.session_state.get("_access_logged"):
        try:
            from app.database import get_db_session
            from app.services.activity_service import ActivityService
            _db = get_db_session()
            try:
                ActivityService(_db).log(email, name, "Login / Acesso ao sistema")
            finally:
                _db.close()
        except Exception:
            pass
        st.session_state["_access_logged"] = True

    return email, name


def sidebar_user():
    """Renders user info and logout button at the bottom of the sidebar."""
    with st.sidebar:
        st.divider()
        st.caption(f"👤 **{st.user.name or st.user.email}**")
        st.caption(st.user.email)
        if st.button("Sair", use_container_width=True):
            st.logout()
