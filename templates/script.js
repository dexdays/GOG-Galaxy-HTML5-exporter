document.addEventListener("DOMContentLoaded", function() {
    const corners     = ['tl', 'tr', 'bl', 'br'];
    const overlay     = document.getElementById('overlay');
    const controls    = document.getElementById('controls');
    const games       = document.getElementById('games');
    const gameList    = games.children;
    const gameSearch  = document.getElementById('search');
    const gameSize    = document.getElementById('width');
    const gameSpacing = document.getElementById('spacing');

    var X = 0,                          // Last known horizontal position
        Y = 0,                          // Last known vertical position
        bCursorShow = true,             // Should the cursor be shown again?
        lastElement = {'id': null};     // Last element with an active tooltip

    function updateTooltipPos(x, y) {
        if (updateTooltipPos.tooltip) {
            const t = updateTooltipPos.tooltip;
            const w = document.documentElement.clientWidth || document.body.clientWidth;
            const h = document.documentElement.clientHeight || document.body.clientHeight;

            // Anchor the tooltip to the right/bottom if the standard orientation overflows
            // the view, and there's enough space to fit it in the other direction.
            const bRight = (w < (x + t.offsetWidth)) && (0 <= (x - t.offsetWidth));
            const bBottom = (h < (y + t.offsetHeight)) && (0 <= (y - t.offsetHeight));
            const pos = bRight + 2 * bBottom;
            var newX = x - (bRight ? t.offsetWidth : 0);
            var newY = y - (bBottom ? t.offsetHeight : 0);
            t.style.top  = newY + 'px';
            t.style.left = newX + 'px';

            for (var i = 0; i < 4; i++) {
                if (i == pos) t.classList.add(corners[i]);
                if (i != pos) t.classList.remove(corners[i]);
            }
        }
    }

    // Return the child element that acts as a tooltip
    function getTooltip(element) {
        for (const child of element.children)
            if (child.classList.contains("data"))
                return child;
        return null;
    }

    /* Set the `min-width` equal to the current width 

       We use `display: none` instead of hiding in order to save
       a lot of time on loading. In order to have both the minimum
       necessary blank space and tooltips not resizing along the edges
       of the screen, we temporarily display & hide to calculate the
       necessary width, before resetting both */
    function initTooltip(element) {
        element.style.visibility = 'hidden';
        element.style.display = 'block';
        element.style.minWidth = element.offsetWidth + 'px';
        element.style.display = null;
        element.style.visibility = null;
    }

    // Wrapper for the continuous update of the range input controls
    function hookRangeChange(r,f) {
        var n,c,m;
        r.addEventListener("input",function(e){n=1;c=e.target.value;if(c!=m)f(e);m=c;});
        r.addEventListener("change",function(e){if(!n)f(e);});
    }

    // Update the game card width
    function onChangeSize(event) {
        games.style.setProperty('--cover-width', event.target.value + 'px');
    }

    // Update the game cards spacing
    function onChangeSpacing(event) {
        games.style.setProperty('--cover-spacing', event.target.value + 'px');
    }

    // Show/hide the input controls
    function onToggleControls(event) {
        if (event.ctrlKey && (32 == event.keyCode))
            controls.classList.toggle('visible');
    }

    // Triggers `onSearch` to clear the search results
    function onSearchCancel(event) {
        setTimeout(onSearch, 10, event);
    }

    // Perform search on the games
    function onSearch(event) {
        var query = event.target.value.toLowerCase().replace(/^\s+|\s+$/g, '').replace(/\s{2,}/g, ' ');
        if (query == onSearch.lastQuery)
            return;
        onSearch.lastQuery = query;
        const bCancelSearch = 0 == query.length;
        games.classList.toggle('search-results', !bCancelSearch);

        if (bCancelSearch) {
            // Reset search results
            for (const o of onSearch.results) {
                gameList[o].classList.remove('hit');
                gameList[o].style.order = null;
            }
            onSearch.results = []
        } else {
            // Build a list of results
            const filteredQuery = query.replace(/\s+/, '.*?');
            var results = [];
            for (var i = 0; i < gameList.length; i++) {
                const searchData = JSON.parse(gameList[i].dataset.search);
                for (const source of searchData) {
                    if (-1 !== source.search(filteredQuery)) {
                        results.push(i);
                        break;
                    }
                }
            }
            // In with the new…
            for (const n of results) {
                if (!onSearch.results.includes(n)) {
                    gameList[n].classList.add('hit');
                    //gameList[o].style.order = /* for future weighted searches */
                }
            }
            // … out with the old
            for (const o of onSearch.results) {
                if (!results.includes(o)) {
                    gameList[o].classList.remove('hit');
                    gameList[o].style.order = null;
                }
            }
            onSearch.results = results;
        }
    }
    onSearch.results = [];  // Init static variable

    // Raycasting for easier tooltip management
    function onMouseEvent(event) {
        // Update coordinates on `mousemove` events
        if ('mousemove' === event.type) {
            X = event.offsetX;
            Y = event.offsetY;
        }

        // Based on current mouse coordinates find the relative game card
        const elements = document.elementsFromPoint(X, Y);
        var element = {'id': null};
        if ('mouseout' !== event.type) {
            for (i in elements) {
                if (elements[i].id.startsWith('game-')) {
                    element = elements[i];
                    break;
                }
            }
        }

        if (element.id == lastElement.id) {
            // We're on the same card as before, update the tooltip position only
            if (element.id)
                updateTooltipPos(X, Y);
        } else {
            // We're not on the same card as before, hide previous card's tooltip
            if (lastElement.id) {
                lastElement.classList.remove('hover');
                setTimeout(function(){
                    if (bCursorShow)
                        overlay.style.cursor = 'initial';
                }, 100);
                bCursorShow = true;
                updateTooltipPos.tooltip = null;
            }

            // If we're on a game card, show its tooltip
            if (element.id) {
                const t = getTooltip(element);
                updateTooltipPos.tooltip = t;
                if ('' === t.style.opacity)
                    initTooltip(t);
                t.style.opacity = 0;
                setTimeout(function(e) {e.style.opacity = 1;}, 25, t);
                updateTooltipPos(X, Y);
                bCursorShow = false;
                overlay.style.cursor = 'none';
                element.classList.add('hover');
            }

            lastElement = element;
        }
    }

    // Setup the handlers
    overlay.addEventListener('mousemove', onMouseEvent);
    overlay.addEventListener('mouseout', onMouseEvent);
    window.addEventListener('scroll', onMouseEvent);
    document.addEventListener('keyup', onToggleControls);
    hookRangeChange(gameSize, onChangeSize);
    hookRangeChange(gameSpacing, onChangeSpacing);
    gameSearch.addEventListener('blur', onSearchCancel);
    gameSearch.addEventListener('input', onSearch);

    // Load finished, animate the game list in
    overlay.style.opacity = 0;
    overlay.style.cursor = 'initial';
});