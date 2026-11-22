const key='simrs_demo_orders_v1';
const initial=[
 {no:'LAB-20261122-001',patient:'Aisyah Putri',rm:'00-12-01',test:'Darah Lengkap',doctor:'dr. Andi Pratama',queue:'B-01',status:'Menunggu',price:75000},
 {no:'LAB-20261122-002',patient:'Rizky Ramadhan',rm:'00-12-02',test:'Glukosa Darah Sewaktu',doctor:'dr. Siti Rahma',queue:'B-02',status:'Dipanggil',price:35000},
 {no:'LAB-20261122-003',patient:'Dewi Lestari',rm:'00-12-03',test:'Kolesterol Total',doctor:'dr. Budi Santoso',queue:'B-03',status:'Selesai',price:50000}
];
let orders;try{orders=JSON.parse(localStorage.getItem(key))||initial}catch(e){orders=initial}
const money=n=>'Rp '+Number(n).toLocaleString('id-ID');
document.getElementById('today').textContent=new Date().toLocaleDateString('id-ID',{day:'numeric',month:'long',year:'numeric'});
function save(){localStorage.setItem(key,JSON.stringify(orders));render()}
function showPage(id){document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('.nav-lab a[data-page]').forEach(x=>x.classList.toggle('on',x.dataset.page===id));render();window.scrollTo(0,0)}
document.querySelectorAll('.nav-lab a[data-page]').forEach(a=>a.addEventListener('click',()=>showPage(a.dataset.page)));
function render(){
 const badge=s=>`<span class="badge ${s==='Selesai'?'text-bg-success':s==='Dipanggil'?'text-bg-info':'text-bg-warning'}">${s}</span>`;
 const rows=orders.map(o=>`<tr><td>${o.no}</td><td>${esc(o.patient)}<div class="muted small">${esc(o.rm)}</div></td><td>${esc(o.test)}</td><td>${o.queue}</td><td>${badge(o.status)}</td><td><button class="btn btn-sm btn-outline-primary" onclick="advance('${o.no}')">Lanjutkan</button></td></tr>`).join('');
 document.getElementById('orderRows').innerHTML=rows||'<tr><td colspan="6">Belum ada order.</td></tr>';
 document.getElementById('recentRows').innerHTML=orders.slice(-5).reverse().map(o=>`<tr><td>${o.no}</td><td>${esc(o.patient)}</td><td>${esc(o.test)}</td><td>${o.queue}</td><td>${badge(o.status)}</td></tr>`).join('');
 document.getElementById('patientRows').innerHTML=[...new Map(orders.map(o=>[o.rm,o])).values()].map(o=>`<tr><td>${esc(o.rm)}</td><td>${esc(o.patient)}</td><td>Data order demo</td></tr>`).join('');
 document.getElementById('billingRows').innerHTML=orders.map(o=>`<tr><td>${o.no}</td><td>${esc(o.patient)}</td><td>${money(o.price)}</td><td><span class="badge text-bg-warning">Belum dibayar</span></td></tr>`).join('');
 document.getElementById('statOrders').textContent=orders.length+9;
 document.getElementById('statWaiting').textContent=orders.filter(o=>o.status==='Menunggu').length;
 document.getElementById('reportCount').textContent=orders.length;
 document.getElementById('reportRevenue').textContent=money(orders.reduce((a,o)=>a+o.price,0));
}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function advance(no){const o=orders.find(x=>x.no===no);if(!o)return;const states=['Menunggu','Dipanggil','Sampel Diambil','Diperiksa','Selesai'];o.status=states[Math.min(states.indexOf(o.status)+1,4)];save()}
document.getElementById('orderForm').addEventListener('submit',e=>{e.preventDefault();const f=new FormData(e.target);const date=new Date(),d=date.toISOString().slice(0,10).replaceAll('-','');const seq=String(orders.length+1).padStart(3,'0');const test=f.get('test');const prices={'Darah Lengkap':75000,'Glukosa Darah Sewaktu':35000,'Kolesterol Total':50000,'Urinalisis':45000};orders.push({no:`LAB-${d}-${seq}`,patient:f.get('patient'),rm:f.get('rm'),doctor:f.get('doctor'),test,queue:`B-${String(orders.length+1).padStart(2,'0')}`,status:'Menunggu',price:prices[test]||0});save();e.target.reset();alert('Order demo berhasil ditambahkan!');showPage('orders')});
document.getElementById('orderFilter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('#orderRows tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q)?'':'none')});
document.getElementById('globalSearch').addEventListener('submit',e=>{e.preventDefault();showPage('orders');document.getElementById('orderFilter').value=document.getElementById('searchInput').value;document.getElementById('orderFilter').dispatchEvent(new Event('input'))});
render();