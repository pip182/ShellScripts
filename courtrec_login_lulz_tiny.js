const rIP=`172.31.${Math.random()*256|0}.${Math.random()*256|0}`,d={odrUser:{id:1,uuid:1,email:"probably.has.admin@suckit.com",name:"Fatty\u00A0McFatterson",slug:"fatty-mcfatterson",details:{ip:rIP,searchCredits:500,canceled:!1,multipleAccounts:null,ipCount:0,isUpsellUser:!0,payOnNextDate:20,isPropertyRecs:!0,siteMarker:"courtrec.com",hasAccess:!0,nextDate:new Date(Date.now()+63115200000).toLocaleDateString(),limitReached:!1,transactions:{hasInitial:!0,hasPdf:!0,hasMulti:!0,hasMultiPermits:!0,hasMultiDeeds:!0,hasMultiOwner:!0,hasComp:!0,hasCompBasic:!0,hasCompStandard:!0,hasCompComprehensive:!0,data:!0}}},puid:"8008135"},s={headerTolken:JSON.stringify({tolken:"5f4c4e44534b49534c4a4d534e485f",ip:rIP,expire:Date.now()+63115200000}),conv_rand:"0.8702942579959103"};Object.entries(d).forEach(([k,v])=>document.cookie=`${k}=${encodeURIComponent(JSON.stringify(v))}; path=/; domain=.courtrec.com;`);Object.entries(s).forEach(([k,v])=>localStorage.setItem(k,v));console.log("Done! Reload page.");
