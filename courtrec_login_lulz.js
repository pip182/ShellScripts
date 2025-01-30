// Function to set a cookie
function setCookie(name, value, domain, path = "/") {
    document.cookie = `${name}=${encodeURIComponent(JSON.stringify(value))}; path=${path}; domain=${domain};`;
}

// Generate random IP address
const ipThird = Math.floor(Math.random() * 256);
const ipFourth = Math.floor(Math.random() * 256);
const randomIP = `172.31.${ipThird}.${ipFourth}`;

// User & Session Data Object
const userId = 1;
const puid = "8008135";
const data = {
    "odrUser": {
        "id": userId,
        "uuid": userId,
        "email": "probably.has.admin@suckit.com",
        "name": "Fatty\u00A0McFatterson",
        "slug": "fatty-mcfatterson",
        "details": {
            "ip": randomIP,
            "searchCredits": 500,
            "canceled": false,
            "multipleAccounts": null,
            "ipCount": 0,
            "isUpsellUser": true,
            "payOnNextDate": 20,
            "isPropertyRecs": true,
            "siteMarker": "courtrec.com",
            "hasAccess": true,
            "nextDate": new Date(Date.now() + (1000 * 60 * 60 * 24 * 365 * 2)).toLocaleDateString('en-US'),
            "limitReached": false,
            "transactions": {
                "hasInitial": true,
                "hasPdf": true,
                "hasMulti": true,
                "hasMultiPermits": true,
                "hasMultiDeeds": true,
                "hasMultiOwner": true,
                "hasComp": true,
                "hasCompBasic": true,
                "hasCompStandard": true,
                "hasCompComprehensive": true,
                "data": true
            }
        }
    },
    "puid": puid
};

const localStorageValues = {
    "headerTolken": JSON.stringify({
        "tolken": "5f4c4e44534b49534c4a4d534e485f",
        "ip": randomIP,
        "expire": Date.now() + (1000 * 60 * 60 * 24 * 365 * 2) // 2 years from now
    }),
    "conv_rand": "0.8702942579959103"
};

// Set all cookies dynamically
const domain = ".courtrec.com"; // Set domain scope for cookies

for (const [key, value] of Object.entries(data)) {
    setCookie(key, value, domain);
}

// Set values in localStorage
for (const key in localStorageValues) {
    localStorage.setItem(key, localStorageValues[key]);
}

// Log the cookies and localStorage for verification
console.log("Generated Cookies:", document.cookie);
console.log("LocalStorage values:", localStorage);
console.log("%c Reload page to see the magic happen!", "font-weight: bold; font-size: 24px;");
