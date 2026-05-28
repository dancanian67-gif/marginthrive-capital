function scrollToSection(id) {
    document.getElementById(id).scrollIntoView({ behavior: 'smooth' });
}

/* SCROLL REVEAL */
const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add("show");
        }
    });
});

document.querySelectorAll('.reveal').forEach(el => {
    observer.observe(el);
});

function setupSubmissionSuccessModal() {
    const params = new URLSearchParams(window.location.search);
    const submitted = params.get("application_submitted") === "1";
    const modal = document.getElementById("application-success-modal");
    if (!submitted || !modal) {
        return;
    }

    const closeModal = () => {
        modal.hidden = true;
        document.body.classList.remove("modal-open");
        params.delete("application_submitted");
        const nextQuery = params.toString();
        const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}${window.location.hash || ""}`;
        window.history.replaceState({}, "", nextUrl);
    };

    modal.hidden = false;
    document.body.classList.add("modal-open");
    modal.querySelectorAll("[data-close-modal='true']").forEach((element) => {
        element.addEventListener("click", closeModal);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            closeModal();
        }
    });
}

setupSubmissionSuccessModal();