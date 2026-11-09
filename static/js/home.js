document.addEventListener('DOMContentLoaded', () => {
 const slides=[...document.querySelectorAll('.hero-slide')];
 const dots=[...document.querySelectorAll('.slide-dots span')];
 if(slides.length<2) return;
 let index=0;
 setInterval(()=>{
   slides[index].classList.remove('active'); dots[index]?.classList.remove('current');
   index=(index+1)%slides.length;
   slides[index].classList.add('active'); dots[index]?.classList.add('current');
 },4000);
});