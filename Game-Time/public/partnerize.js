// Inject Impact.com / SeatGeek verification meta tags
if (!document.querySelector("meta[name='impact-site-verification']")) {
    var head = document.getElementsByTagName('head')[0];
    
    // Tag 1: Real token
    var meta1 = document.createElement('meta');
    meta1.name = 'impact-site-verification';
    meta1.setAttribute('value', '1b0abe48-699c-47a5-afd2-96fe2538979b');
    head.appendChild(meta1);

    // Tag 2: Fallback for Impact's UI glitch
    var meta2 = document.createElement('meta');
    meta2.name = 'impact-site-verification';
    meta2.setAttribute('value', 'undefined');
    head.appendChild(meta2);
}
(function () {
    // Define dummy/fallback pzthc function if Partnerize script expects it
    window.pzthc = window.pzthc || function () {};

    var pztt = 3;
    var pztp = {"p":"pzt","mi":0,"ma":99,"e":[]};
    var tid = 'c7b6e1e8-98ca-4d8c-acd9-c2d6c30fc6bd';

    var pzth = function (i) {
        var enc = new TextEncoder();
        var bin = enc.encode(i);
        return window.crypto.subtle.digest('SHA-1', bin).then(function (b) {
            var u = new Uint8Array(b);
            var a = [];
            for (var j = 0; j < u.length; j++) {
                var hex = u[j].toString(16);
                if (hex.length < 2) hex = '0' + hex;
                a.push(hex);
            }
            return a.join('');
        });
    };

    var pzth2d = function (h) {
        return h.slice(0, 6) + 'p.' + h + '.com';
    };

    var pztd = function () {
        var i;
        do {
            i = Math.floor(Math.random() * ((pztp.ma + 1) - pztp.mi)) + pztp.mi;
        } while (pztp.e && pztp.e.indexOf(i) !== -1);
        return pzth(pztp.p + i).then(pzth2d);
    };

    var pzti = function () {
        if (pztt <= 0) return;
        var s = document.createElement('script');
        s.onerror = function () { pztt--; pzti(); };
        s.onload = function () { 
            l = true; 
            if (typeof window.pzthc === 'function') {
                window.pzthc();
            }
        };
        var d;
        pztd().then(function (domain) {
            d = domain;
            s.src = 'https://' + d + '/tag/' + tid;
            document.body.appendChild(s);
        }).catch(function () {
            e.push({ error: 'Load failed from ' + d, parameter: '' });
            if (typeof window.pzthc === 'function') {
                window.pzthc();
            }
        });
    };

    var l = false;
    var e = [];

    window.pztr = window.pztr || function (t, f, m, p) {
        var b = (window.pztb = window.pztb || {});
        var x = (b[t] = b[t] || []);
        x.push({ f: f, m: m, p: p });
    };

    pzti();
})();