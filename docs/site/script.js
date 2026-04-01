// ========================================
// Trackmania 2020 Engine Reference - Script
// ========================================

(function() {
    "use strict";

    // Theme management
    const THEME_KEY = "tm2020-docs-theme";

    function getPreferredTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored) return stored;
        return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }

    function setTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem(THEME_KEY, theme);
        // Swap highlight.js theme
        const link = document.getElementById("hljs-theme");
        if (link) {
            link.href = theme === "light"
                ? "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css"
                : "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css";
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme");
        setTheme(current === "dark" ? "light" : "dark");
    }

    // Initialize theme
    setTheme(getPreferredTheme());

    document.addEventListener("DOMContentLoaded", function() {
        // Theme toggle buttons
        var btns = document.querySelectorAll("#theme-toggle, #theme-toggle-mobile");
        btns.forEach(function(btn) {
            btn.addEventListener("click", toggleTheme);
        });

        // Mobile sidebar
        var menuToggle = document.getElementById("menu-toggle");
        var sidebar = document.getElementById("sidebar");
        var overlay = document.getElementById("overlay");

        if (menuToggle) {
            menuToggle.addEventListener("click", function() {
                sidebar.classList.toggle("open");
                overlay.classList.toggle("active");
            });
        }

        if (overlay) {
            overlay.addEventListener("click", function() {
                sidebar.classList.remove("open");
                overlay.classList.remove("active");
            });
        }

        // Code copy buttons
        document.querySelectorAll(".copy-btn").forEach(function(btn) {
            btn.addEventListener("click", function() {
                var code = btn.parentElement.querySelector("code");
                if (code) {
                    navigator.clipboard.writeText(code.textContent).then(function() {
                        btn.textContent = "Copied!";
                        btn.classList.add("copied");
                        setTimeout(function() {
                            btn.textContent = "Copy";
                            btn.classList.remove("copied");
                        }, 2000);
                    });
                }
            });
        });

        // Syntax highlighting
        if (typeof hljs !== "undefined") {
            document.querySelectorAll("pre code").forEach(function(block) {
                hljs.highlightElement(block);
            });
        }

        // Technical details toggle
        var TECH_TOGGLE_KEY = "tm2020-docs-tech-hidden";
        var techToggleBtn = document.getElementById("tech-toggle");
        var collapsibleSections = document.querySelectorAll("details.collapsed-by-default");

        function setTechSectionsState(hidden) {
            collapsibleSections.forEach(function(el) {
                if (hidden) {
                    el.removeAttribute("open");
                } else {
                    el.setAttribute("open", "");
                }
            });
            if (techToggleBtn) {
                var icon = techToggleBtn.querySelector(".toggle-icon");
                if (hidden) {
                    techToggleBtn.classList.add("collapsed");
                    icon.innerHTML = "&#9654;";
                    techToggleBtn.childNodes[techToggleBtn.childNodes.length - 1].textContent = " Show Technical Details";
                } else {
                    techToggleBtn.classList.remove("collapsed");
                    icon.innerHTML = "&#9660;";
                    techToggleBtn.childNodes[techToggleBtn.childNodes.length - 1].textContent = " Hide Technical Details";
                }
            }
            localStorage.setItem(TECH_TOGGLE_KEY, hidden ? "1" : "0");
        }

        // Initialize: default is hidden (collapsed), respect stored preference
        var techHidden = localStorage.getItem(TECH_TOGGLE_KEY);
        if (techHidden === null) {
            // Default: collapsed (hidden)
            setTechSectionsState(true);
        } else {
            setTechSectionsState(techHidden === "1");
        }

        if (techToggleBtn) {
            techToggleBtn.addEventListener("click", function() {
                var isCurrentlyHidden = techToggleBtn.classList.contains("collapsed");
                setTechSectionsState(!isCurrentlyHidden);
            });
        }

        // Address toggle (show/hide hex addresses alongside symbol names)
        var ADDR_TOGGLE_KEY = "tm2020-docs-addr-visible";
        var addrToggleBtn = document.getElementById("addr-toggle");

        function setAddrState(visible) {
            if (visible) {
                document.body.classList.add("show-addresses");
            } else {
                document.body.classList.remove("show-addresses");
            }
            if (addrToggleBtn) {
                var icon = addrToggleBtn.querySelector(".toggle-icon");
                if (visible) {
                    addrToggleBtn.classList.remove("collapsed");
                    icon.innerHTML = "&#9660;";
                    addrToggleBtn.childNodes[addrToggleBtn.childNodes.length - 1].textContent = " Hide Hex Addresses";
                } else {
                    addrToggleBtn.classList.add("collapsed");
                    icon.innerHTML = "&#9654;";
                    addrToggleBtn.childNodes[addrToggleBtn.childNodes.length - 1].textContent = " Show Hex Addresses";
                }
            }
            localStorage.setItem(ADDR_TOGGLE_KEY, visible ? "1" : "0");
        }

        // Initialize: default is hidden (only names shown)
        var addrVisible = localStorage.getItem(ADDR_TOGGLE_KEY);
        if (addrVisible === null) {
            setAddrState(false);
        } else {
            setAddrState(addrVisible === "1");
        }

        if (addrToggleBtn) {
            addrToggleBtn.addEventListener("click", function() {
                var isCurrentlyVisible = document.body.classList.contains("show-addresses");
                setAddrState(!isCurrentlyVisible);
            });
        }

        // Scroll to top button
        var scrollTopBtn = document.getElementById("scroll-top");
        var content = document.getElementById("content");

        function checkScroll() {
            if (window.scrollY > 400) {
                scrollTopBtn.classList.add("visible");
            } else {
                scrollTopBtn.classList.remove("visible");
            }
        }

        window.addEventListener("scroll", checkScroll);
        checkScroll();

        if (scrollTopBtn) {
            scrollTopBtn.addEventListener("click", function() {
                window.scrollTo({ top: 0, behavior: "smooth" });
            });
        }

        // ToC active highlighting + auto-open collapsed sections on click
        var tocLinks = document.querySelectorAll(".page-toc a");
        var headings = [];

        tocLinks.forEach(function(link) {
            var id = link.getAttribute("href");
            if (id && id.startsWith("#")) {
                var el = document.getElementById(id.slice(1));
                if (el) headings.push({ el: el, link: link });
            }

            // When clicking a ToC link, open any collapsed parent <details>
            link.addEventListener("click", function() {
                var targetId = link.getAttribute("href");
                if (targetId && targetId.startsWith("#")) {
                    var target = document.getElementById(targetId.slice(1));
                    if (target) {
                        var parent = target.closest("details.collapsible");
                        if (parent && !parent.hasAttribute("open")) {
                            parent.setAttribute("open", "");
                        }
                        // Also check if the heading is inside a summary
                        var summaryParent = target.closest("summary");
                        if (summaryParent) {
                            var detailsEl = summaryParent.closest("details.collapsible");
                            if (detailsEl && !detailsEl.hasAttribute("open")) {
                                detailsEl.setAttribute("open", "");
                            }
                        }
                    }
                }
            });
        });

        function updateActiveToc() {
            var scrollPos = window.scrollY + 100;
            var active = null;

            for (var i = headings.length - 1; i >= 0; i--) {
                if (headings[i].el.offsetTop <= scrollPos) {
                    active = headings[i];
                    break;
                }
            }

            tocLinks.forEach(function(link) { link.classList.remove("active"); });
            if (active) active.link.classList.add("active");
        }

        if (headings.length > 0) {
            window.addEventListener("scroll", updateActiveToc);
            updateActiveToc();
        }

        // Search functionality
        var searchInput = document.getElementById("search-input");
        var searchResults = document.getElementById("search-results");

        // Build search index from page content
        var searchIndex = [];

        // Index all headings on the current page
        document.querySelectorAll("h1, h2, h3, h4").forEach(function(h) {
            searchIndex.push({
                text: h.textContent.replace(/^#\s*/, ""),
                id: h.id,
                page: "",
                type: "heading"
            });
        });

        // Static cross-page search data
        var pages = [
            { file: "index.html", title: "Overview", keywords: "master overview executive summary binary protection engine architecture class system subsystem map critical addresses open questions" },
            { file: "binary.html", title: "Binary Analysis", keywords: "PE header sections imports exports entry point TLS callbacks packer protector DLL function statistics string statistics" },
            { file: "class-hierarchy.html", title: "Class System", keywords: "CMwNod class hierarchy RTTI MwClassId CGame CPlug CWebServices CNet CScene CHms CControl CSystem namespace vtable" },
            { file: "physics.html", title: "Physics & Vehicle", keywords: "NSceneDyna NSceneVehiclePhy NHmsCollision physics simulation vehicle wheel suspension turbo boost gravity collision friction surface" },
            { file: "rendering.html", title: "Rendering & Graphics", keywords: "D3D11 deferred shading G-buffer HBAO bloom shadows particles volumetric fog SSR PBR lightmap shader HLSL Tech3" },
            { file: "architecture.html", title: "Architecture", keywords: "entry point WinMain CGbxApp game loop state machine CGameCtnApp fiber coroutine ManiaScript profiling initialization" },
            { file: "file-formats.html", title: "File Formats", keywords: "GBX GameBox header chunk serialization CClassicArchive class ID map loading pack Fid CSystemArchiveNod FACADE01" },
            { file: "networking.html", title: "Networking", keywords: "Winsock libcurl OpenSSL HTTP QUIC TCP UDP Ubisoft Connect Nadeo Services authentication API XMPP Vivox XML-RPC" },
            { file: "game-files.html", title: "Game Files", keywords: "DLL materials packs game files analysis Stadium items vehicles textures sounds" },
            { file: "tmnf-crossref.html", title: "TMNF Comparison", keywords: "TrackMania Nations Forever TMNF cross-reference comparison evolution changes" },
        ];

        if (searchInput) {
            searchInput.addEventListener("input", function() {
                var query = searchInput.value.toLowerCase().trim();
                searchResults.innerHTML = "";

                if (query.length < 2) {
                    searchResults.classList.remove("active");
                    return;
                }

                var results = [];

                // Search current page headings
                searchIndex.forEach(function(item) {
                    if (item.text.toLowerCase().includes(query)) {
                        results.push({
                            text: item.text,
                            url: "#" + item.id,
                            page: "(this page)"
                        });
                    }
                });

                // Search cross-page
                pages.forEach(function(page) {
                    if (page.title.toLowerCase().includes(query) ||
                        page.keywords.toLowerCase().includes(query)) {
                        results.push({
                            text: page.title,
                            url: page.file,
                            page: page.file
                        });
                    }
                });

                if (results.length === 0) {
                    searchResults.classList.remove("active");
                    return;
                }

                // Limit results
                results = results.slice(0, 15);

                results.forEach(function(r) {
                    var a = document.createElement("a");
                    a.className = "search-result-item";
                    a.href = r.url;
                    a.innerHTML = r.text + ' <span class="result-page">' + r.page + "</span>";
                    searchResults.appendChild(a);
                });

                searchResults.classList.add("active");
            });

            // Close search on click outside
            document.addEventListener("click", function(e) {
                if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                    searchResults.classList.remove("active");
                }
            });

            // Close search on Escape
            searchInput.addEventListener("keydown", function(e) {
                if (e.key === "Escape") {
                    searchResults.classList.remove("active");
                    searchInput.blur();
                }
            });
        }
    });
})();
