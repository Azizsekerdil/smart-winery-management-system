/**
 * Eğitim modülü içeriği (Türkçe + İngilizce).
 *
 * İçerik burada tutulur, sunucuda değil: uygulamayla birlikte gelir, sürüm
 * kontrollüdür ve çevrimdışı çalışır. Sunucuda yalnızca kimin neyi tamamladığı
 * saklanır (`/api/v1/training/progress`).
 *
 * Yeni modül eklerken: `kod` benzersiz ve kebab-case olmalı; `roller` boş
 * bırakılırsa modül herkese gösterilir; `adimlar[].ekran` gerçek bir uygulama
 * yolu olmalıdır (kullanıcı oradan doğrudan ekrana geçer).
 */
import type { EgitimModulu } from './egitim-tip'

export const MODULLER: EgitimModulu[] = [
  {
    kod: 'sisteme-giris',
    baslik: { tr: 'Sisteme Giriş, Arayüz ve Rolünüz', en: 'Signing In, the Interface and Your Role' },
    ozet: { tr: 'İlk oturum, menünün rolünüze göre nasıl şekillendiği, dil ve tema tercihi, eğitim kaydınızın nasıl tutulduğu.', en: 'Your first session, how the menu is shaped by your role, language and theme preferences, and how your training record is kept.' },
    roller: ['sistem_yoneticisi', 'isletme_yoneticisi', 'enolog', 'bagcilik_uzmani', 'laboratuvar_teknisyeni', 'mahzen_sorumlusu', 'uretim_operatoru', 'siseleme_personeli', 'depo_sevkiyat', 'satis_personeli', 'muhasebe', 'denetci'],
    sureDk: 8,
    adimlar: [
      {
        baslik: { tr: 'Oturum açın', en: 'Sign in' },
        metin: { tr: 'Giriş ekranında kullanıcı adınızı (ya da e-posta adresinizi) ve parolanızı yazıp "Giriş yap" düğmesine basın. Hesabınızı sistem yöneticisi oluşturur; size verilen ilk parola geçicidir. Art arda beş hatalı denemede hesap bir süreliğine kilitlenir — bu bir arıza değil, kaba kuvvet saldırısına karşı korumadır; süre dolduğunda kilit kendiliğinden kalkar.', en: 'On the sign-in screen type your username (or e-mail address) and password, then press "Sign in". Your account is created by the system administrator and the first password you receive is temporary. After five consecutive failed attempts the account is locked for a while — this is not a fault but brute-force protection; the lock clears itself once the period expires.' },
        ipucu: { tr: 'Parolanızı kendiniz sıfırlayamazsınız. Sistem yöneticisi Kullanıcılar ekranındaki anahtar simgesinden yeni bir geçici parola atar.', en: 'You cannot reset your own password. The system administrator assigns a new temporary password from the key icon on the Users screen.' },
      },
      {
        baslik: { tr: 'Yan menüyü tanıyın', en: 'Get to know the sidebar' },
        metin: { tr: 'Sol menü Genel, Üretim, Kalite, Lojistik, Analiz, Yapay Zekâ ve Sistem gruplarına ayrılmıştır. Menüde yalnızca yetkiniz olan ekranlar görünür; bu yüzden iki kişinin menüsü aynı olmayabilir. Üst çubuktaki menü düğmesi kenar çubuğunu daraltıp genişletir — dar kipte yalnızca simgeler kalır.', en: 'The sidebar is organised into General, Production, Quality, Logistics, Analysis, AI and System groups. Only the screens you are authorised for appear, so two colleagues may see different menus. The menu button in the top bar collapses and expands the sidebar — in collapsed mode only the icons remain.' },
        ekran: '/',
        ipucu: { tr: 'Bir ekranı menüde göremiyorsanız kurulum eksik değildir; rolünüzde o yetki yoktur. Adresi elle yazsanız da "yetkiniz yok" uyarısı alırsınız ve deneme denetim günlüğüne yazılır.', en: 'If a screen is missing from your menu, nothing is broken — your role simply lacks that permission. Typing the address by hand still returns a "not authorised" notice, and the attempt is written to the audit log.' },
      },
      {
        baslik: { tr: 'Üst çubuk: uyarılar, dil, tema, çıkış', en: 'Top bar: alerts, language, theme, sign-out' },
        metin: { tr: 'Üst çubuğun sağ tarafında sırasıyla açık uyarı sayısını gösteren zil simgesi (tıklayınca Kontrol Paneli\'ne götürür), Türkçe/English seçici, açık-koyu tema düğmesi, adınız ve rolünüz ile oturumu kapatma simgesi yer alır. Dil değişimi anında olur; sayfayı yenilemeniz gerekmez.', en: 'On the right of the top bar you will find, in order: a bell showing the number of open alerts (clicking it takes you to the Dashboard), the Türkçe/English selector, the light-dark theme button, your name and role, and the sign-out icon. Language switching is instant; there is no need to reload the page.' },
        ekran: '/',
        ipucu: { tr: 'Tarih ve sayı biçimi seçtiğiniz dile göre değişir, ancak para birimi işletmenin muhasebe birimi olduğu için her dilde TRY kalır.', en: 'Date and number formats follow the selected language, but the currency stays TRY in both, because it is the winery\'s accounting currency.' },
      },
      {
        baslik: { tr: 'Kontrol Panelini okuyun', en: 'Read the Dashboard' },
        metin: { tr: 'Kontrol Paneli işletmenin anlık durumudur: aktif parti sayısı ve hacmi, tank doluluk oranları, devam eden fermantasyonlar ve tahmini bitiş tarihleri, minimum stokun altına düşen kalemler, yaklaşan/geciken işler ve yerel sayısal analizden gelen risk önerileri. Her kartın "Tümünü gör" bağlantısı ilgili ekrana götürür.', en: 'The Dashboard is the live picture of the winery: active lot count and volume, tank fill levels, fermentations in progress with their predicted completion dates, items below minimum stock, upcoming and overdue work, and risk suggestions from the local numerical analysis. Each card\'s "View all" link takes you to the matching screen.' },
        ekran: '/',
        ipucu: { tr: 'Panodaki yapay zekâ önerileri karar destek amaçlıdır; üretim kararını her zaman laboratuvar sonucu ve enolog değerlendirmesiyle birlikte verin.', en: 'The AI suggestions on the Dashboard are decision support only; always combine them with lab results and the winemaker\'s judgement before acting.' },
      },
      {
        baslik: { tr: 'Kişisel arayüz ayarlarınızı yapın', en: 'Set your interface preferences' },
        metin: { tr: 'Ayarlar ekranındaki "Arayüz" kartından Tema (Koyu / Açık / Sistem) ve Dil seçilir. Tercihiniz tarayıcıda saklanır ve sonraki oturumda korunur. Ayarlar ekranının geri kalanı yapay zekâ sağlayıcı yapılandırmasıdır ve ayrı bir yetki ister; o bölümü göremiyorsanız bu normaldir.', en: 'On the Settings screen, the "Interface" card lets you choose the Theme (Dark / Light / System) and the Language. Your preference is stored in the browser and survives into your next session. The rest of the Settings screen is AI provider configuration and requires a separate permission; not seeing it is normal.' },
        ekran: '/ayarlar',
      },
      {
        baslik: { tr: 'Eğitimi tamamlayın ve kaydınızı bırakın', en: 'Complete the training and leave your record' },
        metin: { tr: 'Eğitim ve Kılavuz ekranında "Sadece rolüm" kutusu işaretliyken yalnızca sizi ilgilendiren modüller listelenir; kutuyu kaldırarak tüm modülleri görebilirsiniz. Bir modül kartına tıklayın, adımları "İleri" ile ilerletin, son adımda "Sınava başla" deyin ve "Sınavı bitir" ile tamamlayın. Geçme notu %70\'tir. Sonucunuz sunucuda saklanır ve yalnızca kendi ilerlemenizi görürsünüz; yöneticiler "Ekip durumu" düğmesiyle kimin hangi modülü tamamladığını görebilir — gıda güvenliği denetiminde sorulan "personel eğitildi mi?" sorusunun cevabı budur.', en: 'On the Training & Guide screen the "My role only" checkbox lists just the modules that concern you; clear it to see every module. Open a module card, move through the steps with "Next", press "Start quiz" on the last step and finish with "Finish quiz". The pass mark is 70%. Your result is stored on the server and you only ever see your own progress; managers can use the "Team status" button to see who completed what — this is the answer to the "has the staff been trained?" question in a food-safety audit.' },
        ekran: '/egitim',
        ipucu: { tr: 'Bir modülü tekrar denemek daha önce kazandığınız yüksek puanı silmez; sunucu en iyi sonucu saklar, deneme sayısını ayrıca tutar.', en: 'Retaking a module never erases a higher score you already earned; the server keeps your best result and counts the attempts separately.' },
      },
    ],
    sorular: [
      {
        soru: { tr: 'Menüde "Laboratuvar" bağlantısını göremiyorsunuz. En olası açıklama nedir?', en: 'You cannot see the "Laboratory" link in the menu. What is the most likely explanation?' },
        secenekler: { tr: ['Laboratuvar modülü bu kuruluma dahil edilmemiştir.', 'Rolünüzde laboratuvar okuma yetkisi yoktur; adresi elle yazsanız da "yetkiniz yok" uyarısı alırsınız.', 'Menü yalnızca geniş ekranlarda tüm bağlantıları gösterir.', 'Laboratuvar ekranı yalnızca Türkçe arayüzde açılır.'], en: ['The Laboratory module was not included in this installation.', 'Your role lacks the lab read permission; typing the address by hand still returns a "not authorised" notice.', 'The menu only shows every link on wide screens.', 'The Laboratory screen only opens in the Turkish interface.'] },
        dogru: 1,
        aciklama: { tr: 'Yan menü kullanıcının yetkilerine göre süzülür ve rota ayrıca korunur. Yetkisiz erişim denemesi engellenir ve denetim günlüğüne yazılır.', en: 'The sidebar is filtered by the user\'s permissions and the route is guarded separately. Unauthorised access attempts are blocked and written to the audit log.' },
      },
      {
        soru: { tr: 'Parolanızı unuttunuz. Sistemdeki doğru yol hangisidir?', en: 'You have forgotten your password. What is the correct route in this system?' },
        secenekler: { tr: ['Giriş ekranındaki "Parolamı unuttum" bağlantısını kullanmak.', 'Sistem yöneticisinden Kullanıcılar ekranından size yeni bir geçici parola atamasını istemek.', 'Beş kez yanlış parola girip hesabı sıfırlatmak.', 'Yedekleme ekranından eski parolayı geri yüklemek.'], en: ['Use the "Forgot my password" link on the sign-in screen.', 'Ask the system administrator to assign you a new temporary password from the Users screen.', 'Enter the wrong password five times so the account resets.', 'Restore the old password from the Backup screen.'] },
        dogru: 1,
        aciklama: { tr: 'Parola sıfırlama kullanıcı yönetimi yetkisi ister ve Kullanıcılar ekranındaki anahtar simgesinden yapılır. Beş hatalı deneme hesabı sıfırlamaz, geçici olarak kilitler.', en: 'Resetting a password requires the user-management permission and is done from the key icon on the Users screen. Five failed attempts do not reset an account — they lock it temporarily.' },
      },
      {
        soru: { tr: 'Bir modülün sınavından önce %90, ardından %60 aldınız. Kaydınızda ne görünür?', en: 'You scored 90% on a module quiz and 60% on a later attempt. What does your record show?' },
        secenekler: { tr: ['%60 — her zaman son deneme geçerlidir.', '%90 korunur; deneme sayısı 2 olur.', '%75 — iki denemenin ortalaması alınır.', 'Kayıt silinir, modülü baştan almanız gerekir.'], en: ['60% — the latest attempt always counts.', '90% is kept; the attempt count becomes 2.', '75% — the average of the two attempts.', 'The record is cleared and you must retake the module.'] },
        dogru: 1,
        aciklama: { tr: 'Sunucu en iyi sonucu saklar. Tekrar denemek kazanılmış başarıyı silmez, yalnızca deneme sayacını artırır.', en: 'The server keeps the best result. Retrying never erases an achievement you already earned; it only increments the attempt counter.' },
      },
    ],
  },
  {
    kod: 'uzum-kabulu-parti',
    baslik: { tr: 'Üzüm Kabulü ve Parti Oluşturma', en: 'Grape Intake and Lot Creation' },
    ozet: { tr: 'Kantar kaydından izlenebilir partiye: kabul formu, olgunluk değerleri, kalite sınıfı, QR ve kaynak bağlama.', en: 'From the weighbridge record to a traceable lot: the intake form, maturity readings, quality grade, QR codes and source linking.' },
    roller: ['bagcilik_uzmani', 'enolog', 'uretim_operatoru', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 14,
    adimlar: [
      {
        baslik: { tr: 'Bağ ve Üzüm Kabulü ekranını tanıyın', en: 'Get to know the Vineyard & Grape Intake screen' },
        metin: { tr: 'Bağ ve Üzüm Kabulü ekranı dört sekmeden oluşur: Üzüm Kabulü, Bağlar, Parseller ve Çeşitler. Günlük işiniz "Üzüm Kabulü" sekmesindedir; diğer üçü referans kayıtlarıdır ve kabul formundaki açılır listeleri besler. Bir bağ, parsel ya da çeşit listede yoksa kabul kaydına da bağlanamaz.', en: 'The Vineyard & Grape Intake screen has four tabs: Grape Intake, Vineyards, Parcels and Grape Varieties. Your day-to-day work is on the "Grape Intake" tab; the other three hold reference data and feed the drop-downs on the intake form. If a vineyard, parcel or variety is missing from those lists, it cannot be linked to an intake record either.' },
        ekran: '/bag',
      },
      {
        baslik: { tr: 'Yeni kabul kaydını açın', en: 'Open a new intake record' },
        metin: { tr: '"Üzüm Kabulü" sekmesindeyken sağ üstteki "Üzüm kabulü" düğmesine basın. Açılan pencerede Çeşit alanı zorunludur. Bağ ve Parsel teknik olarak isteğe bağlıdır, ancak izlenebilirliğin kaynağa kadar uzanması için ikisini de doldurun.', en: 'With the "Grape Intake" tab active, press the "Grape intake" button at the top right. In the dialog that opens, Grape variety is mandatory. Vineyard and Parcel are technically optional, but fill both in so that traceability reaches all the way back to the source.' },
        ekran: '/bag',
        ipucu: { tr: 'Bağ ve parsel boş bırakılırsa kayıt yine oluşur, ama parti detayındaki geriye izleme zinciri bağa ve parsele kadar inemez — denetimde kanıtlayamayacağınız tek halka budur.', en: 'Leaving vineyard and parcel empty still saves the record, but the backward trace on the lot detail page cannot reach the vineyard and parcel — that is exactly the link you will not be able to evidence in an audit.' },
      },
      {
        baslik: { tr: 'Kantar ve olgunluk değerlerini girin', en: 'Enter the weighbridge and maturity readings' },
        metin: { tr: 'Hasat tarihi ve Net ağırlık (kg) zorunludur. Ardından numuneden ölçtüğünüz Brix, pH, toplam asitlik ve gelen üzümün sıcaklığını girin; araç plakasını yazmak sevkiyatı sonradan eşleştirmeyi kolaylaştırır. Kalite sınıfı olarak A, B, C ya da Red seçilir; "Red" kabul edilmeyen yükü kayda geçirir — kayıt dışı geri çevirme izlenebilirlik zincirinde boşluk bırakır.', en: 'Harvest date and Net weight (kg) are mandatory. Then enter the Brix, pH, total acidity you measured on a sample and the temperature of the incoming fruit; recording the vehicle plate makes it easy to match the delivery later. For the quality grade choose A, B, C or Rejected — "Rejected" records a load you refused, and turning fruit away without a record leaves a hole in the traceability chain.' },
        ekran: '/bag',
        ipucu: { tr: 'Birim fiyatı boş bırakırsanız bu kabul, parti maliyetine sıfır üzüm maliyetiyle girer ve litre başına maliyet raporu olduğundan düşük görünür.', en: 'If you leave the unit price blank, this intake enters the lot cost with zero fruit cost and the cost-per-litre report will read lower than reality.' },
      },
      {
        baslik: { tr: 'Kaydı doğrulayın ve QR kodunu alın', en: 'Verify the record and get its QR code' },
        metin: { tr: 'Kaydettikten sonra kabul listede kendi kodu ile (örneğin UK-2026-0001) görünür. Satırın sonundaki QR simgesi bu kabul kaydının QR kodunu yeni bir sekmede açar; çıktısını kasaya ya da palete iliştirin. Kalite sınıfı rozeti listede renklidir: A yeşil, B/C turuncu, Red kırmızıdır.', en: 'Once saved, the intake appears in the list with its own code (for example UK-2026-0001). The QR icon at the end of the row opens that intake\'s QR code in a new tab; print it and attach it to the crate or pallet. The quality grade badge is colour-coded in the list: A green, B/C amber, Rejected red.' },
        ekran: '/bag',
      },
      {
        baslik: { tr: 'Partiler ekranında yeni parti açın', en: 'Create a new lot on the Lots screen' },
        metin: { tr: 'Partiler ekranında sağ üstteki "Parti oluştur" düğmesine basın. Parti adını anlamlı yazın (örneğin "Öküzgözü Rezerv 2026"), şarap tipini seçin (Kırmızı / Beyaz / Rose / Köpüklü / Tatlı), başlangıç hacmine şıra litresini girin ve şıranın alınacağı tankı seçin.', en: 'On the Lots screen press "Create lot" at the top right. Give the lot a meaningful name (for example "Öküzgözü Reserve 2026"), choose the wine type (Red / White / Rosé / Sparkling / Sweet), enter the must volume as the initial volume and select the tank the must will go into.' },
        ekran: '/partiler',
      },
      {
        baslik: { tr: 'Kaynak üzüm kabullerini bağlayın', en: 'Link the source grape intakes' },
        metin: { tr: 'Aynı pencerenin "Kaynak üzüm kabulleri" bölümünde açılır listeden bir kabul seçin, o kabulden bu partiye giren kg ve elde edilen şıra litresini yazın. Birden fazla kabulden gelen üzüm varsa "Kaynak ekle" ile yeni satır açın. En az bir geçerli kaynak satırı zorunludur; kaydedilmeden parti oluşmaz.', en: 'In the "Source grape intakes" section of the same dialog, pick an intake from the drop-down and enter the kilograms that went into this lot and the must litres obtained from them. If the fruit comes from several intakes, press "Add source" for another row. At least one valid source row is required; without it the lot is not created.' },
        ekran: '/partiler',
        ipucu: { tr: 'kg ve şıra litresini gerçek değerlerle girin. Bu iki sayı İstatistikler ekranındaki üzümden şişeye fire zincirinin ve litre başına maliyetin temelidir; yaklaşık girilen değer tüm rekolte raporunu bozar.', en: 'Enter the real kilograms and must litres. These two numbers underpin the grape-to-bottle loss chain on the Statistics screen and the cost per litre; a rough guess distorts the whole vintage report.' },
      },
      {
        baslik: { tr: 'Parti detayında izlenebilirliği okuyun', en: 'Read traceability on the lot detail page' },
        metin: { tr: 'Parti listesinde bir satıra tıklayın. Açılan detayda üstte aşama, durum, hacim, tank, pH ve alkol göstergeleri; altında İzlenebilirlik çizgesi bulunur. Sağ üstteki seçiciden Tam izleme, Geriye (kaynağa) veya İleriye (ürüne) yönünü seçin; düğümleri sürükleyebilir, tekerlekle yakınlaştırabilirsiniz. Sayfanın altında işlem geçmişi ve maliyet dağılımı yer alır; "QR kodu" düğmesi partinin kodunu üretir.', en: 'Click a row in the lot list. The detail page shows stage, status, volume, tank, pH and alcohol at the top, with the traceability graph below. Use the selector at the top right to choose Full trace, Backward (to source) or Forward (to product); you can drag the nodes and zoom with the scroll wheel. Further down you will find the operation history and the cost breakdown; the "QR code" button generates the lot\'s code.' },
        ekran: '/partiler',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Üzüm kabul formunda Bağ ve Parsel alanlarını boş bıraktınız. Bunun izlenebilirlik açısından somut sonucu nedir?', en: 'You left the Vineyard and Parcel fields empty on the intake form. What is the concrete consequence for traceability?' },
        secenekler: { tr: ['Kayıt hiç oluşmaz, form kaydedilmez.', 'Kayıt oluşur, ancak parti detayındaki geriye izleme zinciri bağa ve parsele kadar uzanamaz.', 'Kabul kaydı için QR kodu üretilmez.', 'Kalite sınıfı otomatik olarak "Red" atanır.'], en: ['The record is not created at all; the form will not save.', 'The record is created, but the backward trace on the lot detail page cannot reach the vineyard and parcel.', 'No QR code is generated for the intake record.', 'The quality grade is automatically set to "Rejected".'] },
        dogru: 1,
        aciklama: { tr: 'Bu alanlar zorunlu değildir, ama izlenebilirlik çizgesi yalnızca kaydedilmiş bağlantıları çizebilir. Boş bırakılan halka denetimde kanıtlanamaz.', en: 'These fields are not mandatory, but the traceability graph can only draw links that were actually recorded. A missing link cannot be evidenced in an audit.' },
      },
      {
        soru: { tr: 'Bir parti iki ayrı üzüm kabulünden oluşturuluyor. Doğru yöntem hangisidir?', en: 'A lot is being built from two separate grape intakes. What is the correct approach?' },
        secenekler: { tr: ['İki ayrı parti açıp sonra elle birleştirmek.', 'Parti oluştur penceresinde "Kaynak ekle" ile iki kaynak satırı doldurmak.', 'Yalnızca büyük olan kabulü seçip diğerini not alanına yazmak.', 'Önce tank transferi yapıp partiyi sonradan açmak.'], en: ['Create two separate lots and merge them by hand afterwards.', 'Fill in two source rows using "Add source" in the Create lot dialog.', 'Select only the larger intake and mention the other one in the notes.', 'Do the tank transfer first and create the lot afterwards.'] },
        dogru: 1,
        aciklama: { tr: 'Her kaynak satırı çizgede ayrı bir üzüm kabul düğümü olarak partiye bağlanır; not alanına yazılan bilgi izlenebilirlik zincirine girmez.', en: 'Each source row is linked to the lot as its own grape-intake node in the graph; text written in the notes field never enters the traceability chain.' },
      },
      {
        soru: { tr: 'Kaynak satırında elde edilen şıra hacmini olduğundan düşük girmenin en somut sonucu nedir?', en: 'What is the most concrete consequence of under-reporting the must volume on a source row?' },
        secenekler: { tr: ['Parti hiç kaydedilmez.', 'Üzümden şişeye verim/fire zinciri ve litre başına maliyet yanlış hesaplanır.', 'Fermantasyon başlatılamaz.', 'Parti için QR kodu üretilmez.'], en: ['The lot is not saved at all.', 'The grape-to-bottle yield and loss chain and the cost per litre are calculated incorrectly.', 'Fermentation cannot be started.', 'No QR code is generated for the lot.'] },
        dogru: 1,
        aciklama: { tr: 'Fire zinciri ve maliyet hesabı bu sayıyı temel alır. Sistem hesabı doğru yapar; hatalı olan girilen veridir.', en: 'The loss chain and cost calculation are built on this figure. The system does the arithmetic correctly — it is the entered data that is wrong.' },
      },
    ],
  },
  {
    kod: 'tank-yonetimi',
    baslik: { tr: 'Tank Yönetimi ve Transferler', en: 'Tank Management and Transfers' },
    ozet: { tr: 'Yerleşim ve liste görünümü, transfer türleri, fire, ve sistemin transfer öncesi otomatik yaptığı hacim–kapasite–temizlik kontrolleri.', en: 'Layout and list views, transfer types, loss, and the volume, capacity and cleanliness checks the system runs automatically before every transfer.' },
    roller: ['uretim_operatoru', 'mahzen_sorumlusu', 'enolog', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 10,
    adimlar: [
      {
        baslik: { tr: 'Yerleşim görünümünü okuyun', en: 'Read the layout view' },
        metin: { tr: 'Tanklar ekranı varsayılan olarak "Yerleşim" görünümünde açılır ve tankları mahzen bölgelerine göre gruplar. Her kutuda tank kodu, durum rozeti, içindeki parti, dikey doluluk göstergesi, doluluk yüzdesi, mevcut/kapasite litre ve varsa ölçülen sıcaklık ile hedef sıcaklık görünür. Sayfa başlığındaki özet toplam hacmi ve genel doluluk oranını verir.', en: 'The Tanks screen opens in "Layout" view by default and groups tanks by cellar zone. Each tile shows the tank code, a status badge, the lot inside, a vertical fill indicator, the fill percentage, current/capacity litres and, where available, the measured and target temperatures. The summary in the page header gives total volume and overall fill level.' },
        ekran: '/tanklar',
        ipucu: { tr: 'Bir tankın çerçevesi amber renge dönmüşse ölçülen sıcaklık hedeften 3 °C\'den fazla sapmıştır. Soğutmayı kontrol edin — sapma fermantasyonda uçucu asitlik riskinin ilk işaretidir.', en: 'An amber border means the measured temperature has drifted more than 3 °C from target. Check the cooling — that drift is the first sign of volatile acidity risk during fermentation.' },
      },
      {
        baslik: { tr: 'Liste görünümüne geçin', en: 'Switch to the list view' },
        metin: { tr: 'Sağ üstteki "Yerleşim / Liste" düğmesinden Liste görünümüne geçin. Burada kod, tip, kapasite, dolu hacim, doluluk çubuğu, durum, temizlik durumu, içindeki parti, bölge ve son temizlik tarihi sütunları vardır. Arama kutusuna tank kodunu yazarak hızla filtreleyebilirsiniz.', en: 'Use the "Layout / List" toggle at the top right to switch to the list view. It shows code, type, capacity, filled volume, a fill bar, status, cleaning status, the lot inside, zone and the last cleaning date. Type a tank code into the search box to filter quickly.' },
        ekran: '/tanklar',
      },
      {
        baslik: { tr: 'Doğru işlem türünü seçin', en: 'Choose the right operation type' },
        metin: { tr: '"Transfer" düğmesi transfer yetkisi olan kullanıcılarda görünür. Açılan pencerede önce partiyi, sonra işlem türünü seçin: Dolum (tanka giriş — kaynak tank boş bırakılır), Tank arası transfer, Aktarma (tortudan ayırma) ve Boşaltım (hedef tank boş bırakılır).', en: 'The "Transfer" button appears for users with the transfer permission. In the dialog choose the lot first, then the operation type: Fill (into tank — leave the source tank empty), Tank-to-tank transfer, Racking (off the lees) and Emptying (leave the destination tank empty).' },
        ekran: '/tanklar',
      },
      {
        baslik: { tr: 'Hacim ve fireyi ayrı ayrı girin', en: 'Enter volume and loss separately' },
        metin: { tr: 'Hacim (L) alanına kaynak tanktan çıkan miktarı, Fire (L) alanına yolda kaybolan miktarı yazın. Sistem hedef tanka ulaşan miktarı "hacim − fire" olarak hesaplar ve boş kapasite kontrolünü bu değerle yapar. Kaynak tanktan ise tam hacim düşülür.', en: 'Enter the amount leaving the source tank in the Volume (L) field and whatever is lost on the way in the Loss (L) field. The system treats the volume arriving in the destination tank as "volume − loss" and runs the free-capacity check against that figure, while the full volume is deducted from the source tank.' },
        ekran: '/tanklar',
        ipucu: { tr: 'Fireyi sıfır bırakıp hacmi düşük yazarak dengelemeyin. Fire ayrı alanda tutulduğu için parti fire oranı ve maliyet raporları doğru çıkar; hacme gizlenen kayıp raporlarda görünmez.', en: 'Do not compensate by leaving loss at zero and under-reporting the volume. Loss is kept in its own field so that lot loss rates and cost reports stay correct; a loss hidden inside the volume never shows up in reporting.' },
      },
      {
        baslik: { tr: 'Sistemin engellediği durumları tanıyın', en: 'Know what the system will refuse' },
        metin: { tr: 'Kaydete bastığınızda sistem üç şeyi denetler: kaynak tankta yeterli hacim var mı, hedef tankta yeterli boş kapasite var mı ve hedef tank temiz mi. Boş ve temizlik durumu "kirli" olan bir tanka dolum yapılamaz; devre dışı bırakılmış bir tank da hedef seçilemez. Bu durumlarda ekranda hangi tankın hangi nedenle engellediğini söyleyen bir hata kutusu çıkar.', en: 'When you save, the system checks three things: is there enough volume in the source tank, enough free capacity in the destination tank, and is the destination tank clean. An empty tank whose cleaning status is "dirty" cannot be filled, and a decommissioned tank cannot be chosen as the destination. In each case an error box tells you which tank blocked the transfer and why.' },
        ekran: '/tanklar',
        ipucu: { tr: 'Kirli tank engeline takıldıysanız Bakım ve Temizlik ekranından o tank için bir CIP ya da temizlik kaydı girin; kayıt tamamlandığında tankın temizlik durumu güncellenir ve transfer geçer.', en: 'If a dirty-tank block stops you, record a CIP or cleaning entry for that tank on the Maintenance & Cleaning screen; once the record is completed the tank\'s cleaning status updates and the transfer goes through.' },
      },
      {
        baslik: { tr: 'Transfer sonrasını doğrulayın', en: 'Verify the outcome of the transfer' },
        metin: { tr: 'Transfer kaydedildiğinde tank doluluk oranları, partinin bağlı olduğu tank kodu ve partinin izlenebilirlik çizgesi birlikte güncellenir. Yerleşim görünümünde iki tankın doluluk göstergesinin değiştiğini, Partiler ekranında ise partinin Tank sütununun yeni tankı gösterdiğini kontrol edin.', en: 'When the transfer is saved, tank fill levels, the tank code attached to the lot and the lot\'s traceability graph are all updated together. Check that the fill indicators of both tanks have changed in the layout view, and that the Tank column on the Lots screen now shows the new tank.' },
        ekran: '/tanklar',
      },
    ],
    sorular: [
      {
        soru: { tr: '500 L\'lik bir transferde 5 L fire girdiniz. Sistem hesabı nasıl yapar?', en: 'You record a 500 L transfer with 5 L of loss. How does the system do the arithmetic?' },
        secenekler: { tr: ['Hedefe 500 L gelir, kaynaktan 505 L düşer.', 'Hedefe 495 L gelir, kaynaktan 500 L düşer.', 'Hedefe 500 L gelir, kaynaktan 500 L düşer; fire yalnızca not amaçlıdır.', 'Hedefe 505 L gelir, kaynaktan 500 L düşer.'], en: ['500 L arrives at the destination and 505 L is deducted from the source.', '495 L arrives at the destination and 500 L is deducted from the source.', '500 L arrives and 500 L is deducted; the loss field is for information only.', '505 L arrives at the destination and 500 L is deducted from the source.'] },
        dogru: 1,
        aciklama: { tr: 'Hedefe ulaşan hacim "hacim − fire" olarak hesaplanır ve boş kapasite kontrolü bu değerle yapılır; kaynak tanktan tam hacim düşülür.', en: 'The volume arriving is calculated as "volume − loss" and the free-capacity check uses that figure, while the full volume leaves the source tank.' },
      },
      {
        soru: { tr: 'Boş ve temizlik durumu "kirli" olan bir tanka dolum yapmak istiyorsunuz. Ne olur?', en: 'You try to fill a tank that is empty and whose cleaning status is "dirty". What happens?' },
        secenekler: { tr: ['İşlem kaydedilir, tank otomatik olarak temiz sayılır.', 'İşlem reddedilir; önce Bakım ve Temizlik ekranından temizlik ya da CIP kaydı girilmelidir.', 'İşlem kaydedilir ama parti karantinaya alınır.', 'İşlem yalnızca enolog onayıyla kaydedilir.'], en: ['The transfer is saved and the tank is automatically treated as clean.', 'The transfer is refused; a cleaning or CIP record must first be entered on the Maintenance & Cleaning screen.', 'The transfer is saved but the lot is put into quarantine.', 'The transfer is saved only with the winemaker\'s approval.'] },
        dogru: 1,
        aciklama: { tr: 'Temizlik denetimi kod düzeyindedir ve atlanamaz. Bu kural, temizlenmemiş bir tanka şarap alınmasını fiziksel olarak değil ama kayıt düzeyinde engeller.', en: 'The cleanliness check is enforced in code and cannot be bypassed. It prevents wine being recorded into an uncleaned tank in the first place.' },
      },
      {
        soru: { tr: 'Tank yerleşiminde bir tankın çerçevesi amber renkte. Bu ne anlama gelir?', en: 'A tank tile in the layout view has an amber border. What does that mean?' },
        secenekler: { tr: ['Tank tamamen doludur.', 'Ölçülen sıcaklık hedef sıcaklıktan 3 °C\'den fazla sapmıştır.', 'Tank devre dışı bırakılmıştır.', 'Tankta kupaj yapılmıştır.'], en: ['The tank is completely full.', 'The measured temperature has drifted more than 3 °C from the target temperature.', 'The tank has been decommissioned.', 'A blend was executed in this tank.'] },
        dogru: 1,
        aciklama: { tr: 'Sıcaklık sapması görsel olarak öne çıkarılır çünkü fermantasyon sırasında en hızlı müdahale gerektiren durumdur.', en: 'Temperature drift is highlighted visually because it is the condition that demands the fastest intervention during fermentation.' },
      },
    ],
  },
  {
    kod: 'fermantasyon-takibi',
    baslik: { tr: 'Fermantasyon Takibi ve Ölçüm Girişi', en: 'Fermentation Monitoring and Recording Readings' },
    ozet: { tr: 'Fermantasyon başlatma, günlük ölçüm girişi, eğri okuma, sıcaklık bandı alarmları ve tahmini bitiş hesabı.', en: 'Starting a fermentation, entering daily readings, reading the curve, temperature-band alarms and the predicted completion date.' },
    roller: ['uretim_operatoru', 'laboratuvar_teknisyeni', 'enolog', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Devam eden fermantasyonları listeleyin', en: 'List the fermentations in progress' },
        metin: { tr: 'Fermantasyon ekranı varsayılan olarak "Devam ediyor" filtresiyle açılır. Tabloda kod, parti, tank, tür, durum, son Brix / hedef Brix, son sıcaklık, ilerleme çubuğu ve açık anomali sayısı görünür. Üstteki durum seçicisinden Tümü, Tamamlandı, Planlandı ya da Durakladı filtrelerine geçebilirsiniz.', en: 'The Fermentation screen opens with the "In progress" filter applied. The table shows code, lot, tank, type, status, last Brix / target Brix, last temperature, a progress bar and the number of open anomalies. Use the status selector above the table to switch to All, Completed, Planned or Stalled.' },
        ekran: '/fermantasyon',
      },
      {
        baslik: { tr: 'Yeni fermantasyon başlatın', en: 'Start a new fermentation' },
        metin: { tr: 'Sağ üstteki "Fermantasyon başlat" düğmesine basın. Parti zorunludur; tank, hacim ve başlangıç Brix değerini girin. Hedef Brix alanı kuru şaraplar için varsayılan olarak -1 gelir — şeker tükendiğinde refraktometre okuması sıfırın altına indiği için bu normaldir. Min. ve maks. sıcaklık alanları alarm bandını belirler, maya suşunu da yazın.', en: 'Press "Start fermentation" at the top right. The lot is mandatory; enter the tank, volume and initial Brix. The target Brix field defaults to -1 for dry wines — that is normal, because the refractometer reading drops below zero once the sugar is consumed. The min. and max. temperature fields define the alarm band; record the yeast strain as well.' },
        ekran: '/fermantasyon',
        ipucu: { tr: 'Sıcaklık bandını gerçekçi girin. Bandı gereğinden geniş tutarsanız hiç alarm almazsınız; gereğinden dar tutarsanız gerçek sorunları gürültü içinde kaybedersiniz.', en: 'Set a realistic temperature band. Too wide and you will never see an alarm; too narrow and real problems drown in noise.' },
      },
      {
        baslik: { tr: 'Günlük ölçümü girin', en: 'Enter the daily reading' },
        metin: { tr: 'Tabloda bir satıra tıklayınca altta o fermantasyonun eğri kartı açılır. Kartın sağ üstündeki "Ölçüm gir" düğmesi yalnızca fermantasyon devam ederken ve yazma yetkiniz varsa görünür. Formda sıcaklık, Brix, yoğunluk, pH, uçucu asitlik ve serbest SO₂ alanları vardır; en az birini doldurmanız yeterlidir, boş alanlar eğriye eklenmez.', en: 'Clicking a row opens that fermentation\'s curve card below the table. The "Enter reading" button at the top right of the card only appears while the fermentation is in progress and you hold the write permission. The form has temperature, Brix, density, pH, volatile acidity and free SO₂ fields; filling in just one is enough, and empty fields are simply not plotted.' },
        ekran: '/fermantasyon',
        ipucu: { tr: 'Ölçmediğiniz bir parametreye sıfır yazmayın. Boş bırakmak "ölçülmedi" demektir; sıfır ise gerçek bir ölçüm gibi eğriye işlenir ve yanlış anomali üretir.', en: 'Never type zero for a parameter you did not measure. Empty means "not measured"; zero is plotted as a genuine reading and will trigger a false anomaly.' },
      },
      {
        baslik: { tr: 'Şapka yönetimini kaydedin', en: 'Record cap management' },
        metin: { tr: 'Kırmızı şaraplarda "Şapka yönetimi" alanına o günkü uygulamayı yazın: Pigeage (şapka batırma), Remontage (üstten çevirme) ya da Délestage (boşalt-doldur). Bu kayıt ekstraksiyon geçmişinin tek yazılı kanıtıdır ve sonraki rekoltelerde tanen profili tartışıldığında başvurulacak veridir.', en: 'For red wines, record the day\'s practice in the "Cap management" field: pigeage (punch-down), remontage (pump-over) or délestage (rack-and-return). This entry is the only written evidence of the extraction history and is what you will refer back to when the tannin profile is discussed in later vintages.' },
        ekran: '/fermantasyon',
      },
      {
        baslik: { tr: 'Eğriyi ve alarmları okuyun', en: 'Read the curve and the alarms' },
        metin: { tr: 'Eğri kartında Brix, sıcaklık ve pH birlikte çizilir. Hedef Brix yatay bir çizgi, sıcaklık bandı ise yeşilimsi bir alan olarak gösterilir; sıcaklık bu alanın dışına çıktığında tablodaki değer amber renge döner ve uyarı simgesi belirir. Anomali sayısı sütunu, sayısal çekirdeğin yakaladığı sıra dışı ölçümleri sayar.', en: 'The curve card plots Brix, temperature and pH together. The target Brix appears as a horizontal line and the temperature band as a green-tinted area; when the temperature leaves that band the value in the table turns amber with a warning icon. The anomaly column counts the unusual readings caught by the numerical core.' },
        ekran: '/fermantasyon',
      },
      {
        baslik: { tr: 'Tahmini bitiş tarihini kullanın', en: 'Use the predicted completion date' },
        metin: { tr: 'Yeterli ölçüm biriktiğinde eğrinin altında tahmini bitiş tarihi ve kısa bir hesap notu belirir. Bu tahmin, girilen ölçümler üzerinden çalışan yerel sayısal hesaba dayanır; dil modeli kapalıyken de üretilir ve dış servise veri göndermez. Tank ve iş gücü planlamasında kullanın, ama şeker tükendiğini yalnızca laboratuvar sonucuyla ilan edin.', en: 'Once enough readings have accumulated, a predicted completion date and a short calculation note appear beneath the curve. The prediction comes from a local numerical calculation over the readings you entered; it is produced even when the language model is switched off and no data leaves the machine. Use it for tank and labour planning, but only declare dryness on the basis of a lab result.' },
        ekran: '/fermantasyon',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Kuru bir kırmızı şarap için fermantasyon başlatıyorsunuz. Hedef Brix alanına ne yazmak uygundur?', en: 'You are starting a fermentation for a dry red wine. What is an appropriate value for the target Brix field?' },
        secenekler: { tr: ['22 civarı bir değer.', '-1 ile 0 arasında bir değer.', 'Başlangıç Brix ile aynı değer.', 'Alan boş bırakılır; sistem sonradan sorar.'], en: ['Something around 22.', 'A value between -1 and 0.', 'The same value as the initial Brix.', 'Leave it empty; the system will ask later.'] },
        dogru: 1,
        aciklama: { tr: 'Şeker tükendiğinde alkolün etkisiyle refraktometre okuması sıfırın altına iner; bu yüzden kuru şaraplarda hedef Brix negatiftir ve alan varsayılan olarak -1 gelir.', en: 'Once the sugar is consumed, the alcohol pushes the refractometer reading below zero, which is why dry wines carry a negative target Brix — the field defaults to -1.' },
      },
      {
        soru: { tr: 'O gün pH ölçmediniz. Ölçüm formunda ne yapmalısınız?', en: 'You did not measure pH that day. What should you do on the reading form?' },
        secenekler: { tr: ['pH alanına 0 yazmak.', 'pH alanını boş bırakmak; boş alan eğriye eklenmez.', 'Bir önceki günün pH değerini tekrar yazmak.', 'Ölçüm girmeyi tamamen atlamak.'], en: ['Type 0 into the pH field.', 'Leave the pH field empty; empty fields are not plotted.', 'Repeat yesterday\'s pH value.', 'Skip entering a reading altogether.'] },
        dogru: 1,
        aciklama: { tr: 'En az bir ölçüm değeri yeterlidir. Sıfır yazmak ya da eski değeri tekrarlamak eğriyi ve anomali tespitini bozar.', en: 'A single reading value is enough to save the form. Typing zero or repeating an old value corrupts both the curve and the anomaly detection.' },
      },
      {
        soru: { tr: 'Fermantasyon eğrisindeki "Tahmini bitiş" bilgisi neye dayanır?', en: 'What is the "Predicted completion" figure on the fermentation curve based on?' },
        secenekler: { tr: ['Bulut yapay zekâ modeline; sağlayıcı kapalıysa hiç görünmez.', 'Girilen ölçümler üzerinden çalışan yerel sayısal hesaba; dil modeli kapalıyken de üretilir.', 'Reçetede tanımlı sabit gün sayısına.', 'Tankın kapasitesine ve tipine.'], en: ['A cloud AI model; it disappears when the provider is disabled.', 'A local numerical calculation over the readings you entered; it is produced even with the language model switched off.', 'A fixed number of days defined in the recipe.', 'The tank\'s capacity and type.'] },
        dogru: 1,
        aciklama: { tr: 'Sayısal çekirdek dil modelinden bağımsızdır. Bu sayede tahmin, anomali tespiti ve risk puanı sağlayıcı kapalıyken de çalışır ve veri makineden çıkmaz.', en: 'The numerical core is independent of any language model, so predictions, anomaly detection and risk scoring keep working with every provider disabled — and no data leaves the machine.' },
      },
    ],
  },
  {
    kod: 'laboratuvar-analizi',
    baslik: { tr: 'Laboratuvar Analizi ve Onay Akışı', en: 'Laboratory Analysis and the Approval Workflow' },
    ozet: { tr: 'Numune alma, analiz sonucu girişi, spesifikasyon denetimi ve görevler ayrılığına dayanan onay/red akışı.', en: 'Taking samples, entering analysis results, specification checking and the approve/reject workflow built on segregation of duties.' },
    roller: ['laboratuvar_teknisyeni', 'enolog', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Üç sekmeyi ayırt edin', en: 'Tell the three tabs apart' },
        metin: { tr: 'Laboratuvar ekranı üç sekmeden oluşur. "Sonuçlar" tamamlanmış analizleri ve onay durumlarını listeler; "Numuneler" alınmış ama henüz sonucu girilmemiş numuneleri gösterir; "Spesifikasyonlar" ise her parametre için alt-üst sınırları ve seviyeyi tanımlar. Sonuçlar bu spesifikasyonlara göre otomatik denetlenir.', en: 'The Laboratory screen has three tabs. "Results" lists completed analyses and their approval status; "Samples" shows samples that have been drawn but not yet analysed; "Specifications" defines the lower and upper limits and severity for each parameter. Results are checked automatically against those specifications.' },
        ekran: '/laboratuvar',
      },
      {
        baslik: { tr: 'Numune alın', en: 'Take a sample' },
        metin: { tr: 'Sağ üstteki "Numune al" düğmesine basın. Partiyi seçin ve numune türünü belirtin: Rutin, Kontrol, Şişeleme öncesi ya da Şikâyet. "Numuneyi kaydet ve sonuç gir" dediğinizde numune kaydı oluşur ve analiz sonucu penceresi doğrudan açılır.', en: 'Press "Take sample" at the top right. Choose the lot and state the sample type: Routine, Control, Pre-bottling or Complaint. When you press "Save sample and enter results" the sample record is created and the analysis form opens straight away.' },
        ekran: '/laboratuvar',
        ipucu: { tr: 'Sonucu hemen girmeyecekseniz pencereyi kapatın; numune "Numuneler" sekmesinde bekler ve oradaki "Sonuç gir" düğmesiyle daha sonra tamamlanır.', en: 'If you are not entering results immediately, close the dialog; the sample waits on the "Samples" tab and can be completed later with its "Enter result" button.' },
      },
      {
        baslik: { tr: 'Analiz sonucunu girin', en: 'Enter the analysis result' },
        metin: { tr: 'Sonuç formunda pH, toplam asitlik, uçucu asitlik, serbest SO₂, toplam SO₂, alkol, kalıntı şeker, yoğunluk, malik asit ve bulanıklık alanları vardır. Yalnızca gerçekten ölçtüğünüz parametreleri doldurun. Malik asit değeri malolaktik fermantasyonun tamamlanıp tamamlanmadığını gösterdiği için dinlendirme aşamasındaki partilerde özellikle önemlidir.', en: 'The result form covers pH, total acidity, volatile acidity, free SO₂, total SO₂, alcohol, residual sugar, density, malic acid and turbidity. Fill in only the parameters you actually measured. Malic acid matters especially for lots in ageing, since it shows whether malolactic fermentation has finished.' },
        ekran: '/laboratuvar',
      },
      {
        baslik: { tr: 'Spesifikasyon işaretlerini okuyun', en: 'Read the specification flags' },
        metin: { tr: 'Sonuç kaydedildiği anda spesifikasyonlara göre denetlenir. Sınır dışına çıkan satır kırmızımsı zeminle gösterilir ve onay sütununun altında "Spesifikasyon dışı" etiketi belirir; etiketin üzerine gelince hangi parametrenin hangi sınırı aştığını okuyabilirsiniz. Uçucu asitlik 0,90 g/L ve üzerindeyse ayrıca kalın kırmızı yazılır.', en: 'As soon as a result is saved it is checked against the specifications. A row that falls outside the limits is shown on a red-tinted background with an "Out of spec" label under the approval column; hover over the label to read which parameter breached which limit. Volatile acidity of 0.90 g/L or more is additionally shown in bold red.' },
        ekran: '/laboratuvar',
        ipucu: { tr: 'Spesifikasyon dışı bir sonucu "düzeltmek" için sınırları genişletmeyin. Sınır değişikliği tüm geçmiş yorumunu bozar; doğru yol partiyi enologa bildirmektir.', en: 'Never widen a limit to make an out-of-spec result go away. Changing a specification rewrites the interpretation of your whole history; the right move is to escalate the lot to the winemaker.' },
      },
      {
        baslik: { tr: 'Onay ya da red işleyin', en: 'Process the approval or rejection' },
        metin: { tr: 'Onay filtresini "Onay bekleyen" yapın. Onay yetkisi olan kullanıcılarda her satırın işlem sütununda onay (✓) ve red (✗) düğmeleri görünür. Reddederken sistem gerekçe ister ve gerekçe yazılmadan işlem tamamlanmaz. Zaten onaylanmış ya da reddedilmiş bir sonuç ikinci kez işlenemez.', en: 'Set the approval filter to "Pending approval". Users with the approval permission see approve (✓) and reject (✗) buttons in the action column of each row. Rejecting requires a reason, and the action will not complete without one. A result that has already been approved or rejected cannot be processed a second time.' },
        ekran: '/laboratuvar',
        ipucu: { tr: 'Analizi giren kişi kendi sonucunu onaylayamaz. Bu bir hata değil, görevler ayrılığı kuralıdır; onay başka bir yetkili kullanıcıdan gelmelidir.', en: 'The person who entered an analysis cannot approve their own result. That is not a bug but segregation of duties; approval must come from a different authorised user.' },
      },
      {
        baslik: { tr: 'Yapay zekâ yorumunu isteğe bağlı kullanın', en: 'Use the AI commentary as an option' },
        metin: { tr: 'Satırdaki kıvılcım simgesi partinin analiz profilini yorumlar: önce yerel sayısal puanlama tablosu (parametre, değer, ideal aralık, puan), ardından varsa dil modelinin metin yorumu görünür. Pencerenin altındaki sorumluluk notunu okuyun — bu çıktı karar destek amaçlıdır ve onay yerine geçmez.', en: 'The sparkle icon on a row interprets the lot\'s analysis profile: first a local numerical scoring table (parameter, value, ideal range, score) and then, where available, a written commentary from the language model. Read the disclaimer at the bottom of the dialog — this output is decision support and never a substitute for approval.' },
        ekran: '/laboratuvar',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Analizi siz girdiniz ve onay kuyruğunda kendi sonucunuzu görüyorsunuz. Onay düğmesine bastığınızda ne olur?', en: 'You entered an analysis and now see your own result in the approval queue. What happens when you press approve?' },
        secenekler: { tr: ['Sonuç onaylanır ve iş akışı tamamlanır.', 'Sistem işlemi reddeder: analizi yapan kişi kendi sonucunu onaylayamaz.', 'Sonuç onaylanır ama denetim günlüğüne yazılmaz.', 'Sonuç otomatik olarak reddedilmiş sayılır.'], en: ['The result is approved and the workflow completes.', 'The system refuses: the analyst cannot approve their own result.', 'The result is approved but is not written to the audit log.', 'The result is automatically treated as rejected.'] },
        dogru: 1,
        aciklama: { tr: 'Görevler ayrılığı kuralıdır: onay, laboratuvar onay yetkisi olan başka bir kullanıcıdan gelmelidir. Böylece tek kişi hem ölçüp hem kendi ölçümünü serbest bırakamaz.', en: 'This is segregation of duties: approval must come from a different user holding the lab approval permission, so that no single person can both measure and release their own measurement.' },
      },
      {
        soru: { tr: 'Kaydettiğiniz analiz satırı kırmızı zeminle ve "Spesifikasyon dışı" etiketiyle işaretlendi. İlk yapmanız gereken nedir?', en: 'Your saved analysis row is highlighted in red with an "Out of spec" label. What should you do first?' },
        secenekler: { tr: ['Satırı silip değerleri yeniden girmek.', 'Etiketin üzerine gelip hangi parametrenin sınırı aştığını okumak ve partiyi enologa bildirmek.', 'Spesifikasyonlar sekmesinden ilgili sınırı genişletmek.', 'Sonucu onaylamak; işaret yalnızca bilgi amaçlıdır.'], en: ['Delete the row and re-enter the values.', 'Hover over the label to see which parameter breached its limit, then escalate the lot to the winemaker.', 'Widen the relevant limit on the Specifications tab.', 'Approve the result; the flag is informational only.'] },
        dogru: 1,
        aciklama: { tr: 'Spesifikasyon denetimi sizi uyarmak içindir. Sınırı değiştirmek ya da kaydı silmek sorunu değil yalnızca uyarıyı ortadan kaldırır.', en: 'The specification check exists to warn you. Changing the limit or deleting the record removes the warning, not the problem.' },
      },
      {
        soru: { tr: '"Numuneyi kaydet ve sonuç gir" dediğinizde ne olur?', en: 'What happens when you press "Save sample and enter results"?' },
        secenekler: { tr: ['Yalnızca numune kaydı oluşur; sonuç girişi ancak ertesi gün açılır.', 'Numune kaydı oluşur ve analiz sonucu penceresi doğrudan açılır.', 'Numune ve içi sıfırlarla dolu bir analiz sonucu birlikte oluşturulur.', 'Numune doğrudan onay kuyruğuna gönderilir.'], en: ['Only the sample record is created; results can be entered the next day.', 'The sample record is created and the analysis result dialog opens immediately.', 'A sample and a result filled with zeros are created together.', 'The sample goes straight into the approval queue.'] },
        dogru: 1,
        aciklama: { tr: 'Numune kaydedilir kaydedilmez sonuç formu açılır. Sonradan girmek isterseniz Numuneler sekmesindeki "Sonuç gir" düğmesini kullanın.', en: 'The result form opens the moment the sample is saved. To enter results later, use the "Enter result" button on the Samples tab.' },
      },
    ],
  },
  {
    kod: 'recete-kupaj',
    baslik: { tr: 'Reçete, Kupaj ve Onay', en: 'Recipes, Blending and Approval' },
    ozet: { tr: 'Kupaj senaryosu kurma, hacim ağırlıklı öngörüleri okuma, yetkili onayı ve kupajın partilere etkisi.', en: 'Building a blend scenario, reading the volume-weighted predictions, obtaining approval and understanding what executing a blend does to the lots.' },
    roller: ['enolog', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Kupaj ve reçete sekmelerini ayırın', en: 'Separate the blending and recipe tabs' },
        metin: { tr: 'Reçete ve Kupaj ekranı iki sekmeden oluşur. "Kupaj Senaryoları" mevcut partileri birleştirme denemelerinizi tutar; "Reçeteler" ise versiyonlu ürün reçetelerini, bileşen ve katkı listelerini, satır maliyetlerini ve süreç adımlarını gösterir. Kupaj senaryosu bir denemedir; uygulanana kadar hiçbir partiye dokunmaz.', en: 'The Recipes and Blending screen has two tabs. "Blend Scenarios" holds your trials for combining existing lots; "Recipes" shows versioned product recipes with their component and additive lists, line costs and process steps. A blend scenario is only a trial — it touches no lot until it is executed.' },
        ekran: '/recete',
      },
      {
        baslik: { tr: 'Kupaj senaryosu oluşturun', en: 'Create a blend scenario' },
        metin: { tr: '"Kupaj Senaryoları" sekmesindeyken sağ üstteki "Kupaj senaryosu" düğmesine basın. Senaryoya anlaşılır bir ad verin ve isterseniz hedef tankı şimdiden seçin — açılır listede her tankın boş kapasitesi litre olarak yazar. Bileşen bölümünde en az iki kaynak parti seçmeniz ve her biri için hacim girmeniz gerekir; "Bileşen ekle" ile satır çoğaltılır.', en: 'On the "Blend Scenarios" tab press "Blend scenario" at the top right. Give the scenario a clear name and, if you wish, pick the target tank right away — the drop-down shows each tank\'s free capacity in litres. In the component section you must choose at least two source lots and enter a volume for each; use "Add component" to add rows.' },
        ekran: '/recete',
        ipucu: { tr: 'Aynı partilerle farklı oranları denemek için ayrı senaryolar açın. Senaryolar uygulanana kadar üretimi etkilemediği için yan yana karşılaştırmak serbesttir.', en: 'Create separate scenarios to trial different proportions of the same lots. Scenarios have no effect on production until executed, so comparing them side by side costs nothing.' },
      },
      {
        baslik: { tr: 'Öngörüleri doğru yorumlayın', en: 'Interpret the predictions correctly' },
        metin: { tr: 'Her senaryo kartında dört gösterge vardır: tahmini alkol, pH, TA (toplam asitlik) ve tahmini maliyet. Bu değerler bileşen partilerin son bilinen değerlerinden hacim ağırlıklı olarak hesaplanır. Kartın altındaki not bunun bir öngörü olduğunu hatırlatır — kupaj uygulandıktan sonra sonucu mutlaka laboratuvar analiziyle doğrulayın.', en: 'Each scenario card carries four figures: predicted alcohol, pH, TA (total acidity) and estimated cost. They are calculated as volume-weighted averages of the component lots\' last known values. The note under the card reminds you these are predictions — always confirm the outcome with a lab analysis after the blend is executed.' },
        ekran: '/recete',
      },
      {
        baslik: { tr: 'Yetkili onayını alın', en: 'Obtain authorised approval' },
        metin: { tr: 'Senaryo "Senaryo" ya da "Onay bekliyor" durumundayken, kupaj onay yetkisi olan kullanıcıda kartın altında "Onayla" ve "Reddet" düğmeleri görünür. Onay verilene kadar uygulama düğmesi hiç çıkmaz; bu, kupaj gibi geri dönüşü olmayan bir işlemin tek kişinin kararıyla yapılmasını engeller.', en: 'While a scenario is in "Scenario" or "Pending approval" status, a user holding the blend approval permission sees "Approve" and "Reject" buttons at the bottom of the card. The execute button does not appear at all until approval is given — this prevents an irreversible operation like blending from resting on one person\'s decision.' },
        ekran: '/recete',
      },
      {
        baslik: { tr: 'Kupajı uygulayın', en: 'Execute the blend' },
        metin: { tr: 'Durum "Onaylandı" olduğunda kartta "Kupajı uygula" düğmesi belirir. Açılan pencerede sonuç partisinin adını ve hedef tankı girin. Uygulandığında kaynak partilerden ilgili hacimler düşülür, yeni bir sonuç partisi oluşur, maliyet bu partiye taşınır ve izlenebilirlik çizgesinde kaynak partilerden yeni partiye giden bağlantılar oluşur.', en: 'Once the status is "Approved", the "Execute blend" button appears on the card. In the dialog enter the name of the result lot and the target tank. On execution the relevant volumes are deducted from the source lots, a new result lot is created, cost is carried across to it, and links from the source lots to the new lot appear in the traceability graph.' },
        ekran: '/recete',
        ipucu: { tr: 'Kaynak partilerden birinde senaryoda yazdığınız hacim kalmamışsa sistem uygulamayı reddeder ve hangi partide ne kadar eksik olduğunu söyler. Senaryo eskimişse hacimleri güncelleyin.', en: 'If one of the source lots no longer holds the volume written into the scenario, the system refuses to execute and tells you which lot is short and by how much. Update the volumes if the scenario has gone stale.' },
      },
      {
        baslik: { tr: 'Reçeteleri inceleyin', en: 'Review the recipes' },
        metin: { tr: '"Reçeteler" sekmesinde her kart bir reçetenin belirli bir versiyonunu gösterir (kod, ad ve v1, v2 gibi versiyon numarası). Tabloda bileşen adı, türü, oran ya da miktar ve satır maliyeti; altında numaralandırılmış süreç adımları ve her adımın gün cinsinden süresi bulunur. Onaylanmış reçetelerde yeşil rozet görünür.', en: 'On the "Recipes" tab each card shows one version of a recipe (code, name and a version number such as v1 or v2). The table lists component name, kind, proportion or amount and line cost; underneath are numbered process steps with the duration of each in days. Approved recipes carry a green badge.' },
        ekran: '/recete',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Kupaj kartında görünen tahmini alkol ve pH değerleri neyi ifade eder?', en: 'What do the predicted alcohol and pH figures on a blend card represent?' },
        secenekler: { tr: ['Laboratuvarda ölçülmüş kesin değerleri.', 'Bileşen partilerin son değerlerinden hacim ağırlıklı hesaplanan öngörüyü; uygulamadan sonra laboratuvar doğrulaması gerekir.', 'Reçetede elle girilmiş hedef değerleri.', 'Geçen rekoltenin aynı ürün için ortalamasını.'], en: ['Exact values measured in the laboratory.', 'A volume-weighted prediction from the component lots\' last values; lab confirmation is still required after execution.', 'Target values typed in by hand in the recipe.', 'Last vintage\'s average for the same product.'] },
        dogru: 1,
        aciklama: { tr: 'Öngörü planlama içindir ve kartın altındaki not bunu açıkça belirtir. Kupaj uygulandıktan sonra sonuç partisinden numune alıp analiz edin.', en: 'The prediction is for planning, as the note under the card states explicitly. After executing the blend, draw a sample from the result lot and analyse it.' },
      },
      {
        soru: { tr: 'Senaryo "Senaryo" durumundayken "Kupajı uygula" düğmesi görünmüyor. Neden?', en: 'The "Execute blend" button is missing while the scenario is in "Scenario" status. Why?' },
        secenekler: { tr: ['Hedef tank seçilmemiştir.', 'Uygulama yalnızca "Onaylandı" durumundaki senaryolarda mümkündür; önce yetkili onayı gerekir.', 'Bileşen sayısı üçten azdır.', 'Senaryonun adı çok kısadır.'], en: ['The target tank has not been selected.', 'Execution is only possible for scenarios in "Approved" status; authorised approval must come first.', 'There are fewer than three components.', 'The scenario name is too short.'] },
        dogru: 1,
        aciklama: { tr: 'Kupaj geri alınamaz bir işlemdir. Bu yüzden akış senaryo → onay → uygulama sırasına bağlanmıştır ve onaysız uygulama sunucu tarafında da reddedilir.', en: 'Blending is irreversible, so the flow is bound to the order scenario → approval → execution, and an unapproved execution is refused on the server as well.' },
      },
      {
        soru: { tr: 'Kupaj uygulandığında partilere ne olur?', en: 'What happens to the lots when a blend is executed?' },
        secenekler: { tr: ['Kaynak partiler değişmez; yalnızca rapora bir kayıt düşer.', 'Kaynak partilerden ilgili hacimler düşer, yeni bir sonuç partisi oluşur ve maliyet bu partiye taşınır.', 'Kaynak partiler silinir ve yerlerini sonuç partisi alır.', 'Yalnızca hedef tankın doluluk oranı güncellenir.'], en: ['The source lots are untouched; only a reporting entry is made.', 'The relevant volumes are deducted from the source lots, a new result lot is created and cost is carried across to it.', 'The source lots are deleted and replaced by the result lot.', 'Only the destination tank\'s fill level is updated.'] },
        dogru: 1,
        aciklama: { tr: 'Kaynak partiler silinmez; kalan hacimleriyle var olmaya devam eder ve izlenebilirlik çizgesinde sonuç partisine bağlanır.', en: 'Source lots are never deleted; they continue to exist with their remaining volume and stay linked to the result lot in the traceability graph.' },
      },
    ],
  },
  {
    kod: 'fici-mahzen',
    baslik: { tr: 'Fıçı ve Mahzen Yönetimi', en: 'Barrel and Cellar Management' },
    ozet: { tr: 'Mahzen haritası, fıçı hareket türleri, topping ve fire takibi, meşe/kavurma/yaş bilgisinin okunması.', en: 'The cellar map, barrel movement types, topping up and loss tracking, and how to read oak, toast and age information.' },
    roller: ['mahzen_sorumlusu', 'enolog', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 10,
    adimlar: [
      {
        baslik: { tr: 'Mahzen haritasını okuyun', en: 'Read the cellar map' },
        metin: { tr: 'Fıçı ve Mahzen ekranı "Mahzen haritası" görünümünde açılır ve fıçıları mahzen bölgelerine göre gruplar. Sayfa başlığındaki özet dolu fıçı sayısını, toplam hacmi ve toplam fireyi verir. Her fıçı kutusunda dolulukla orantılı bir gösterge, fıçı kodu, içindeki parti (ya da meşe türü) ve olgunlaşma gün sayısı yer alır.', en: 'The Barrels and Cellar screen opens in "Cellar map" view, grouping barrels by cellar zone. The summary in the page header gives the number of filled barrels, total volume and total loss. Each barrel tile shows a fill indicator, the barrel code, the lot inside (or the oak type) and the number of days of ageing.' },
        ekran: '/fici',
      },
      {
        baslik: { tr: 'Fıçı hareketi penceresini açın', en: 'Open the barrel movement dialog' },
        metin: { tr: 'Fıçı yazma yetkisi olan kullanıcı bir fıçı kutusuna tıkladığında hareket penceresi açılır. Sistem işlem türünü akıllıca ön seçer: fıçı doluysa "Üstünü tamamlama", boşsa "Dolum". Pencerenin üstünde fıçının mevcut hacmi, kapasitesi ve durumu yazar; kaydetmeden önce bunları doğrulayın.', en: 'A user with the barrel write permission opens the movement dialog by clicking a barrel tile. The system pre-selects a sensible movement type: "Topping up" if the barrel is full, "Fill" if it is empty. The dialog header shows the barrel\'s current volume, capacity and status — check these before saving.' },
        ekran: '/fici',
      },
      {
        baslik: { tr: 'Doğru hareket türünü seçin', en: 'Choose the right movement type' },
        metin: { tr: 'Altı hareket türü vardır. Dolum boş fıçıya şarap alır ve parti seçimi zorunludur. Üstünü tamamlama (topping), buharlaşmayla oluşan boşluğu aynı şaraptan az miktarla doldurur. Boşaltım fıçıyı tortudan ayırarak boşaltır. Aktarma başka bir kaba geçiş, Temizlik ve Onarım ise fıçının bakım kayıtlarıdır.', en: 'There are six movement types. Fill puts wine into an empty barrel and requires a lot to be selected. Topping up replaces the ullage created by evaporation with a small amount of the same wine. Racking empties the barrel off its lees. Transfer moves the wine to another vessel, while Cleaning and Repair record barrel upkeep.' },
        ekran: '/fici',
        ipucu: { tr: 'Topping işleminde parti alanı zorunlu değildir, ama aynı partiden tamamladığınızı kaydetmek izlenebilirliği bozmadan tutmanın tek yoludur.', en: 'The lot field is optional for topping up, but recording that you topped from the same lot is the only way to keep traceability intact.' },
      },
      {
        baslik: { tr: 'Fireyi her harekette kaydedin', en: 'Record loss on every movement' },
        metin: { tr: 'Fıçıda buharlaşma kaçınılmazdır ve "melek payı" olarak bilinen bu kayıp maliyete doğrudan yansır. Her harekette Fire (L) alanına gerçek kaybı yazın; sistem bunu fıçı satırındaki toplam fireye ve mahzen özetindeki genel fire toplamına ekler. Böylece hangi bölgenin ya da hangi fıçı grubunun daha çok kaybettiğini görebilirsiniz.', en: 'Evaporation in barrel is unavoidable, and this "angels\' share" feeds straight into cost. Record the real loss in the Loss (L) field on every movement; the system adds it to the barrel\'s total loss and to the overall loss figure in the cellar summary. That is how you find out which zone or barrel group is losing the most.' },
        ekran: '/fici',
      },
      {
        baslik: { tr: 'Liste görünümünde fıçı künyesini inceleyin', en: 'Inspect the barrel record in list view' },
        metin: { tr: 'Sağ üstteki "Mahzen haritası / Liste" düğmesinden liste görünümüne geçin. Sütunlarda meşe türü, üretici (cooper), kavurma seviyesi, fıçı yaşı, kapasite, dolu hacim, durum, içindeki parti, olgunlaşma gün sayısı ve toplam fire vardır. Satır sonundaki QR simgesi fıçının etiketini üretir; yeni fıçılar mahzene girdiğinde bu kodu fıçının kafasına yapıştırın.', en: 'Use the "Cellar map / List" toggle at the top right to switch to list view. The columns cover oak type, cooper, toast level, barrel age, capacity, filled volume, status, the lot inside, days of ageing and total loss. The QR icon at the end of the row produces the barrel\'s label — stick it on the barrel head when new barrels arrive in the cellar.' },
        ekran: '/fici',
        ipucu: { tr: 'Fıçı yaşı tadım notlarını yorumlarken belirleyicidir: birinci dolum bir fıçının verdiği meşe etkisiyle dördüncü dolumunki aynı değildir. Yaş ve dolum sayısını liste görünümünden kontrol edin.', en: 'Barrel age is decisive when interpreting tasting notes: the oak influence of a first-fill barrel is nothing like that of a fourth-fill. Check age and fill count in the list view.' },
      },
    ],
    sorular: [
      {
        soru: { tr: 'Dolu bir fıçının kartına tıkladığınızda işlem türü varsayılan olarak "Üstünü tamamlama" gelir. Bunun üretimdeki karşılığı nedir?', en: 'Clicking a full barrel pre-selects "Topping up" as the movement type. What does that correspond to in the cellar?' },
        secenekler: { tr: ['Fıçının tamamen boşaltılması.', 'Buharlaşmayla oluşan boşluğun aynı şaraptan az miktarla doldurulması.', 'Fıçının içinin yıkanması.', 'Şarabın başka bir fıçıya aktarılması.'], en: ['Emptying the barrel completely.', 'Replacing the ullage created by evaporation with a small amount of the same wine.', 'Washing out the barrel.', 'Moving the wine into another barrel.'] },
        dogru: 1,
        aciklama: { tr: 'Dolu bir fıçıda en sık yapılan iş toppingdir; sistem bu yüzden dolu fıçılarda bu türü ve küçük bir varsayılan hacmi ön seçer.', en: 'Topping up is by far the most frequent operation on a full barrel, which is why the system pre-selects that type and a small default volume.' },
      },
      {
        soru: { tr: 'Fıçı hareketlerinde "Fire (L)" alanını sürekli boş bırakırsanız hangi bilgi bozulur?', en: 'If you always leave the "Loss (L)" field empty on barrel movements, which information becomes unreliable?' },
        secenekler: { tr: ['Fıçının kapasitesi ve meşe türü.', 'Mahzen özetindeki toplam fire ve parti maliyetindeki litre başına maliyet.', 'Fıçının QR kodu.', 'Olgunlaşma gün sayısı.'], en: ['The barrel\'s capacity and oak type.', 'The total loss in the cellar summary and the cost per litre in the lot costing.', 'The barrel\'s QR code.', 'The number of days of ageing.'] },
        dogru: 1,
        aciklama: { tr: 'Kaydedilmeyen fire, litre başına maliyeti olduğundan düşük gösterir ve yıl sonunda beklenmedik bir hacim açığı olarak karşınıza çıkar.', en: 'Unrecorded loss makes the cost per litre look lower than it is and turns up as an unexplained volume shortfall at the end of the year.' },
      },
      {
        soru: { tr: 'Bir fıçıyı tortudan ayırıp şarabı tanka almak istiyorsunuz. Hangi hareket türü doğrudur?', en: 'You want to take the wine off its lees and move it from barrel to tank. Which movement type is correct?' },
        secenekler: { tr: ['Dolum', 'Boşaltım', 'Temizlik', 'Onarım'], en: ['Fill', 'Racking', 'Cleaning', 'Repair'] },
        dogru: 1,
        aciklama: { tr: 'Boşaltım (racking) fıçının içeriğini tortu üzerinden alarak boşaltan işlemdir; Temizlik ve Onarım fıçının kendisine yapılan bakım kayıtlarıdır.', en: 'Racking is the operation that empties the barrel off its lees; Cleaning and Repair are upkeep records for the vessel itself.' },
      },
    ],
  },
  {
    kod: 'siseleme-paketleme',
    baslik: { tr: 'Şişeleme ve Paketleme', en: 'Bottling and Packaging' },
    ozet: { tr: 'Şişeleme emri, ambalaj bileşenleri, hat başlatma ve bitirme, verim–fire okuma, etiket önizleme ve LOT numarası.', en: 'Bottling orders, packaging components, starting and finishing the line, reading yield and scrap, label preview and the LOT number.' },
    roller: ['siseleme_personeli', 'enolog', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Şişeleme emrini oluşturun', en: 'Create the bottling order' },
        metin: { tr: 'Şişeleme ekranında sağ üstteki "Şişeleme emri" düğmesine basın. Şişelenecek partiyi seçin — açılır listede her partinin mevcut hacmi litre olarak yazar. Ürün adını etikette görünecek şekilde yazın, planlanan şişe adedini, şişe hacmini (varsayılan 750 ml), koli başına şişe adedini ve hat kodunu girin.', en: 'On the Bottling screen press "Bottling order" at the top right. Choose the lot to be bottled — the drop-down shows each lot\'s current volume in litres. Enter the product name exactly as it should appear on the label, then the planned bottle count, the bottle volume (750 ml by default), bottles per case and the line code.' },
        ekran: '/siseleme',
        ipucu: { tr: 'Planlanan şişe adedi × şişe hacmi partinin mevcut hacmini aşmamalıdır. Hesabı önce yapın: 1.500 şişe × 750 ml = 1.125 L.', en: 'Planned bottles × bottle volume must not exceed the lot\'s available volume. Do the arithmetic first: 1,500 bottles × 750 ml = 1,125 L.' },
      },
      {
        baslik: { tr: 'Ambalaj bileşenlerini bağlayın', en: 'Link the packaging components' },
        metin: { tr: 'Formun "Ambalaj bileşenleri" bölümünde şişe, mantar/kapak, kapsül, etiket ve koli kalemlerini stok kartlarından seçin; listede yalnızca ambalaj kategorisindeki kalemler görünür. Bu seçimler şişeleme bitirildiğinde stoktan otomatik düşülecek kalemlerdir. Ürünün barkodunu da bu bölümde girin.', en: 'In the "Packaging components" section of the form, pick the bottle, cork/closure, capsule, label and case items from the stock catalogue; only items in the packaging category appear in the lists. These are the items that will be deducted from inventory when bottling is finished. Enter the product barcode here as well.' },
        ekran: '/siseleme',
        ipucu: { tr: 'Ambalaj seçmeden emri oluşturursanız emir yine çalışır, ama bitirmede stoktan hiçbir şey düşmez; stok seviyeleri ve şişe başına maliyet gerçeği yansıtmaz.', en: 'You can create an order without selecting packaging, but then nothing is deducted at finish; stock levels and cost per bottle will not reflect reality.' },
      },
      {
        baslik: { tr: 'Hattı başlatın', en: 'Start the line' },
        metin: { tr: 'Emir listede "Planlandı" durumunda görünür. Hat gerçekten çalışmaya başladığında satırın işlem sütunundaki oynat (▶) düğmesine basın; durum "Devam ediyor" olur. Bu düğmeye erkenden basmayın — başlangıç saati hat verimliliği hesabında kullanılır.', en: 'The order appears in the list with status "Planned". When the line actually starts running, press the play (▶) button in the action column; the status changes to "In progress". Do not press it early — the start time feeds the line efficiency calculation.' },
        ekran: '/siseleme',
      },
      {
        baslik: { tr: 'Şişelemeyi bitirin', en: 'Finish the bottling run' },
        metin: { tr: 'Vardiya bittiğinde satırdaki onay (✓) düğmesine basın. Açılan pencerede üretilen şişe adedini, reddedilen şişeleri ve litre cinsinden fireyi girin, bitmiş ürünün alınacağı hedef depoyu seçin, kalite kontrolden geçtiyse ilgili kutuyu işaretleyip notunuzu yazın. Kaydettiğinizde sistem üç işi birlikte yapar: ambalajı stoktan düşer, bitmiş ürünü depoya alır ve partinin hacmini günceller.', en: 'At the end of the shift press the check (✓) button on the row. In the dialog enter the bottles produced, the rejected bottles and the loss in litres, choose the destination warehouse for the finished goods and, if the run passed quality control, tick the box and add your note. On save the system does three things at once: it deducts the packaging from inventory, receives the finished goods into the warehouse and updates the lot volume.' },
        ekran: '/siseleme',
        ipucu: { tr: 'Reddedilen şişe ile fire (L) farklı şeylerdir. Reddedilen, doldurulmuş ama satılamaz şişedir; fire ise hatta kalan ve şişeye hiç girmeyen şaraptır.', en: 'Rejected bottles and loss (L) are not the same thing. A rejected bottle was filled but cannot be sold; loss is wine left in the line that never reached a bottle.' },
      },
      {
        baslik: { tr: 'Verim ve fire yüzdelerini okuyun', en: 'Read the yield and scrap percentages' },
        metin: { tr: 'Emir tamamlandığında tabloda verim ve fire yüzdeleri hesaplanır. Verim, planlanan şişeye göre gerçekleşen üretimi; fire ise reddedilen şişelerin oranını gösterir. LOT numarası emir oluşturulduğunda otomatik üretilir ve tabloda tek aralıklı yazıyla görünür — geri çağırma durumunda aranacak numara budur.', en: 'When an order is completed, the yield and scrap percentages are calculated in the table. Yield compares actual production with the planned bottle count; scrap shows the proportion of rejected bottles. The LOT number is generated automatically when the order is created and appears in monospace in the table — that is the number searched for in a recall.' },
        ekran: '/siseleme',
      },
      {
        baslik: { tr: 'Etiketi önizleyin ve QR kodunu alın', en: 'Preview the label and get the QR code' },
        metin: { tr: 'Satırdaki etiket simgesi ürün etiketinin önizlemesini açar: üretici, ürün adı, rekolte yılı, çeşit, şişe hacmi, alkol derecesi, içindekiler, yasal uyarı metni, LOT numarası ve barkod. Bu önizleme bilgi doğruluğunu ekranda kontrol etmek içindir; matbaa baskısının yerine geçmez. QR simgesi ise şişeleme emrinin QR kodunu ayrı sekmede açar.', en: 'The label icon on the row opens a preview of the product label: producer, product name, vintage year, variety, bottle volume, alcohol level, ingredients, the statutory warning text, the LOT number and the barcode. The preview exists to verify the information on screen and is not a substitute for the print proof. The QR icon opens the bottling order\'s QR code in a separate tab.' },
        ekran: '/siseleme',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Şişeleme emrinde ambalaj bileşenlerini seçmezseniz ne olmaz?', en: 'What does NOT happen if you leave the packaging components unselected on a bottling order?' },
        secenekler: { tr: ['Emir hiç oluşturulamaz.', 'Emir oluşur ama şişeleme bitirildiğinde ambalaj stoktan düşülmez; stok ve şişe başına maliyet gerçeği yansıtmaz.', 'Etiket önizlemesi hiç çalışmaz.', 'LOT numarası üretilmez.'], en: ['The order cannot be created at all.', 'The order is created, but no packaging is deducted at finish; stock levels and cost per bottle no longer reflect reality.', 'The label preview stops working entirely.', 'No LOT number is generated.'] },
        dogru: 1,
        aciklama: { tr: 'Ambalaj bağlantısı stok tüketimini ve maliyet aktarımını sağlar. Bağlantı yoksa emir yine tamamlanır, ama stok sayımınız tutmaz.', en: 'The packaging link is what drives stock consumption and cost allocation. Without it the order still completes, but your stock count will not tally.' },
      },
      {
        soru: { tr: '"Şişelemeyi bitir" penceresini kaydettiğinizde sistem hangi işlemleri birlikte yapar?', en: 'What does the system do when you save the "Finish bottling" dialog?' },
        secenekler: { tr: ['Yalnızca emrin durumunu "Tamamlandı" yapar.', 'Ambalajı stoktan düşer, bitmiş ürünü hedef depoya alır ve partinin hacmini günceller.', 'Yalnızca verim ve fire yüzdelerini hesaplar.', 'Partiyi karantinaya alır ve laboratuvar onayı bekler.'], en: ['It only sets the order status to "Completed".', 'It deducts packaging from inventory, receives the finished goods into the warehouse and updates the lot volume.', 'It only calculates the yield and scrap percentages.', 'It quarantines the lot and waits for lab approval.'] },
        dogru: 1,
        aciklama: { tr: 'Bitirme adımı üretim, stok ve parti hacmini tek işlemde tutarlı hale getirir; bu yüzden gerçek sayılarla ve vardiya bitiminde doldurulmalıdır.', en: 'The finish step reconciles production, inventory and lot volume in a single operation, which is why it must be filled in with real numbers at the end of the shift.' },
      },
      {
        soru: { tr: 'Bir vardiyada 1.000 şişe planlandı, 980 şişe üretildi ve 12 şişe reddedildi. "Fire (L)" alanına ne yazılır?', en: 'A shift planned 1,000 bottles, produced 980 and rejected 12. What goes into the "Loss (L)" field?' },
        secenekler: { tr: ['12 — reddedilen şişe sayısı.', 'Hatta kalan ve hiç şişeye girmeyen şarabın litre cinsinden miktarı.', '20 — planlanan ile üretilen arasındaki fark.', 'Şişe başına 750 ml\'nin toplamı.'], en: ['12 — the number of rejected bottles.', 'The litres of wine left in the line that never reached a bottle.', '20 — the difference between planned and produced.', 'The sum of 750 ml per bottle.'] },
        dogru: 1,
        aciklama: { tr: 'Reddedilen şişeler kendi alanında sayılır. Fire alanı, hat temizliğinde ve dolum başlangıcında kaybedilen sıvı hacmi içindir.', en: 'Rejected bottles are counted in their own field. The loss field is for the liquid volume lost when purging and priming the line.' },
      },
    ],
  },
  {
    kod: 'stok-satinalma-sevkiyat',
    baslik: { tr: 'Stok, Satın Alma ve Sevkiyat', en: 'Inventory, Purchasing and Shipping' },
    ozet: { tr: 'Stok seviyeleri, giriş–çıkış–transfer–sayım işlemleri, FIFO/FEFO mantığı, minimum stok uyarıları ve sevkiyat takibi.', en: 'Stock levels, receipts, issues, transfers and counts, the FIFO/FEFO logic, minimum-stock alerts and shipment tracking.' },
    roller: ['depo_sevkiyat', 'satis_personeli', 'muhasebe', 'siseleme_personeli', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Dört sekmeyi tanıyın', en: 'Get to know the four tabs' },
        metin: { tr: 'Stok ve Sevkiyat ekranı dört sekmeden oluşur: Stok Seviyeleri (an itibarıyla ne var), Hareketler (ne oldu), Satın Alma (ne geliyor) ve Sevkiyat (ne gidiyor). Seviyeler sekmesindeki kategori seçicisi Hammadde, Katkı, Sarf, Ambalaj, Bitmiş ürün ve Yedek parça arasında filtreler.', en: 'The Inventory & Shipping screen has four tabs: Stock Levels (what is on hand right now), Movements (what happened), Purchasing (what is coming in) and Shipping (what is going out). The category selector on the Levels tab filters between Raw material, Additive, Consumable, Packaging, Finished goods and Spare parts.' },
        ekran: '/stok',
      },
      {
        baslik: { tr: 'Mal kabulü girin', en: 'Record a goods receipt' },
        metin: { tr: 'Sağ üstteki "Giriş" düğmesine basın. Kalemi ve depoyu seçin, gelen miktarı ve birim maliyeti girin. Son kullanma tarihi olan kalemlerde SKT\'yi mutlaka yazın; parti kodunu boş bırakırsanız sistem kendisi üretir. Birim maliyet, stok değerini ve ilerideki parti maliyetlerini besleyen tek kaynaktır.', en: 'Press "Receipt" at the top right. Choose the item and the warehouse, then enter the incoming quantity and unit cost. For items with a shelf life always record the expiry date; if you leave the batch code blank the system generates one. The unit cost is the only source feeding stock valuation and downstream lot costing.' },
        ekran: '/stok',
        ipucu: { tr: 'Aynı kalemden farklı fiyatlarla gelen sevkiyatları tek girişte birleştirmeyin. Her sevkiyatı ayrı girin ki FIFO sırası ve stok değeri doğru olsun.', en: 'Do not merge deliveries of the same item that arrived at different prices into one receipt. Enter each delivery separately so the FIFO sequence and stock valuation stay correct.' },
      },
      {
        baslik: { tr: 'Stok çıkışında FIFO/FEFO\'yu anlayın', en: 'Understand FIFO/FEFO on stock issues' },
        metin: { tr: '"Çıkış" penceresinde yalnızca kalemi, depoyu ve miktarı girersiniz; hangi yığından düşüleceğini siz seçmezsiniz. Sistem kalemin değerleme yöntemine göre ya giriş sırasına (FIFO) ya da son kullanma tarihine (FEFO) göre yığın seçer ve tüketilen her yığın için ayrı bir hareket kaydı üretir. Bu yüzden 100 kg\'lık tek bir çıkış Hareketler sekmesinde birden fazla satır olarak görünebilir.', en: 'In the "Issue" dialog you only enter the item, the warehouse and the quantity — you do not pick the batch. The system selects batches by receipt order (FIFO) or by expiry date (FEFO), depending on the item\'s valuation method, and creates a separate movement record for every batch consumed. That is why a single 100 kg issue can appear as several rows on the Movements tab.' },
        ekran: '/stok',
      },
      {
        baslik: { tr: 'Transfer ve sayım yapın', en: 'Transfer and count stock' },
        metin: { tr: '"Transfer" penceresinde kaynak ve hedef depoyu seçerek kalemi depolar arasında taşırsınız; toplam stok değişmez, yalnızca yeri değişir. "Sayım" penceresinde ise sayılan gerçek miktarı yazarsınız; sistem sistemdeki miktarla farkı hesaplar ve düzeltme hareketini kendisi kaydeder. Farkı elle giriş ya da çıkış olarak girmeyin.', en: 'The "Transfer" dialog moves an item between warehouses by selecting a source and a destination; total stock does not change, only its location. In the "Count" dialog you enter the real counted quantity; the system works out the difference against the system quantity and books the adjustment itself. Never enter the difference as a manual receipt or issue.' },
        ekran: '/stok',
        ipucu: { tr: 'Sayım farkını düzeltme hareketi olarak bırakmak denetim izini korur: ne zaman, kim, ne kadar fark buldu sorusu sonradan yanıtlanabilir.', en: 'Leaving the count difference as an adjustment movement preserves the audit trail: who found what discrepancy and when can still be answered later.' },
      },
      {
        baslik: { tr: 'Minimum stok uyarılarını takip edin', en: 'Follow the minimum-stock alerts' },
        metin: { tr: 'Stok Seviyeleri tablosunda mevcut miktarı tanımlı minimum stokun altına düşen satırlar amber zeminle ve ünlem simgesiyle işaretlenir. Aynı kalemler Kontrol Paneli\'ndeki kritik stok kartında da listelenir. Depolar sütunu kalemin hangi depoda ne kadar bulunduğunu, SKT sütunu ise en yakın son kullanma tarihini gösterir.', en: 'On the Stock Levels table, rows whose on-hand quantity has fallen below the defined minimum are shown on an amber background with a warning icon. The same items are listed in the critical stock card on the Dashboard. The Warehouses column shows how much sits in each warehouse and the Expiry column shows the nearest expiry date.' },
        ekran: '/stok',
      },
      {
        baslik: { tr: 'Satın alma ve sevkiyat sekmelerini okuyun', en: 'Read the purchasing and shipping tabs' },
        metin: { tr: 'Satın Alma sekmesi tedarikçi, sipariş tarihi, durum rozeti, kalem sayısı, ara toplam ve genel toplamı listeler. Sevkiyat sekmesi müşteri, sipariş tarihi, durum, taşıyıcı ve tutar bilgisini verir. Durum rozetleri yeşile döndüğünde işlem teslim alınmış ya da teslim edilmiş demektir; bekleyen satırlar takip listenizdir.', en: 'The Purchasing tab lists supplier, order date, status badge, line count, subtotal and grand total. The Shipping tab gives customer, order date, status, carrier and amount. A green status badge means the order has been received or delivered; the rows still pending are your follow-up list.' },
        ekran: '/stok',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Stok çıkışında hangi yığından düşüleceğini kim belirler?', en: 'Who decides which batch a stock issue is taken from?' },
        secenekler: { tr: ['Kullanıcı çıkış penceresinde yığını elle seçer.', 'Sistem, kalemin değerleme yöntemine göre FIFO ya da FEFO sırasıyla seçer ve tüketilen her yığın için ayrı hareket üretir.', 'Her zaman en yüksek birim maliyetli yığın seçilir.', 'Depo sorumlusu ay sonunda toplu olarak eşleştirir.'], en: ['The user picks the batch by hand in the issue dialog.', 'The system picks by FIFO or FEFO according to the item\'s valuation method and creates a separate movement for each batch consumed.', 'The batch with the highest unit cost is always chosen.', 'The warehouse clerk reconciles it in bulk at month end.'] },
        dogru: 1,
        aciklama: { tr: 'Yığın seçimi otomatiktir; bu yüzden tek bir çıkış Hareketler sekmesinde birden fazla satır olarak görünebilir. Görülen bu satırlar hata değil, tüketilen yığınlardır.', en: 'Batch selection is automatic, which is why one issue can appear as several rows on the Movements tab. Those rows are not an error — they are the batches consumed.' },
      },
      {
        soru: { tr: 'Sayımda sayılan miktar sistemdekinden düşük çıktı. Ne yapmalısınız?', en: 'A stock count comes out lower than the system quantity. What should you do?' },
        secenekler: { tr: ['Farkı elle "Çıkış" olarak girmek.', 'Sayım penceresine sayılan gerçek miktarı yazmak; sistem farkı düzeltme hareketi olarak kendisi kaydeder.', 'Kalemi silip doğru miktarla yeniden oluşturmak.', 'Hiçbir şey yapmamak; sayım yalnızca raporlama içindir.'], en: ['Enter the difference manually as an "Issue".', 'Enter the real counted quantity in the Count dialog; the system books the difference as an adjustment itself.', 'Delete the item and recreate it with the correct quantity.', 'Do nothing; counts are for reporting only.'] },
        dogru: 1,
        aciklama: { tr: 'Düzeltme hareketi denetim izini korur. Farkı çıkış olarak girmek gerçek tüketim ile sayım farkını birbirine karıştırır.', en: 'The adjustment movement preserves the audit trail. Booking the difference as an issue mixes genuine consumption up with a counting discrepancy.' },
      },
      {
        soru: { tr: 'Stok seviyeleri tablosunda bir satır amber zeminli ve ünlem işaretli. Bu ne demektir?', en: 'A row on the Stock Levels table is amber with a warning icon. What does that mean?' },
        secenekler: { tr: ['Kalemin son kullanma tarihi geçmiştir.', 'Mevcut miktar tanımlı minimum stokun altındadır; aynı kalem Kontrol Paneli\'nde de listelenir.', 'Kalem birden fazla depoda tutulmaktadır.', 'Kalemin birim maliyeti hiç girilmemiştir.'], en: ['The item\'s shelf life has expired.', 'The on-hand quantity is below the defined minimum stock; the same item is also listed on the Dashboard.', 'The item is held in more than one warehouse.', 'No unit cost has ever been entered for the item.'] },
        dogru: 1,
        aciklama: { tr: 'Minimum stok uyarısı satın alma tetikleyicinizdir. Son kullanma tarihi ise ayrı bir sütunda, en yakın SKT olarak gösterilir.', en: 'The minimum-stock alert is your purchasing trigger. Expiry is shown separately, in its own nearest-expiry column.' },
      },
    ],
  },
  {
    kod: 'bakim-temizlik',
    baslik: { tr: 'Bakım, Temizlik ve CIP Kayıtları', en: 'Maintenance, Cleaning and CIP Records' },
    ozet: { tr: 'Ekipman envanteri, geciken bakımlar, kayıt türleri ve CIP kaydının tankın temizlik durumunu nasıl değiştirdiği.', en: 'Equipment inventory, overdue maintenance, record types, and how a CIP record changes a tank\'s cleaning status.' },
    roller: ['uretim_operatoru', 'mahzen_sorumlusu', 'siseleme_personeli', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 10,
    adimlar: [
      {
        baslik: { tr: 'Yaklaşan ve geciken bakımları görün', en: 'See upcoming and overdue maintenance' },
        metin: { tr: 'Bakım ve Temizlik ekranının en üstünde, planlanan bakım tarihi yaklaşan ya da geçmiş ekipmanları listeleyen bir kart vardır. Kart başlığı kaç kaydın geciktiğini ve kaçının yaklaştığını söyler; geciken satırlar amber zeminde "gün gecikti" ibaresiyle gösterilir. Vardiyaya bu kartı okuyarak başlayın.', en: 'At the top of the Maintenance & Cleaning screen sits a card listing equipment whose scheduled maintenance is approaching or already past. The card header tells you how many records are overdue and how many are upcoming; overdue rows appear on an amber background with a "days overdue" note. Start your shift by reading this card.' },
        ekran: '/bakim',
      },
      {
        baslik: { tr: 'Ekipman envanterini inceleyin', en: 'Review the equipment inventory' },
        metin: { tr: '"Ekipmanlar" sekmesinde kod, ad, tür, üretici, durum, son bakım, sonraki bakım ve kalan gün sütunları bulunur. Durum rozeti arızalı ekipmanı kırmızı, çalışan ekipmanı yeşil gösterir. "Bakım Kayıtları" sekmesi ise yapılmış tüm işleri kayıt kodu, tür, başlık, ekipman/tank, başlangıç-bitiş, duruş süresi, maliyet ve sorumlusuyla listeler.', en: 'The "Equipment" tab shows code, name, type, manufacturer, status, last maintenance, next maintenance and days remaining. The status badge is red for faulty equipment and green for equipment in service. The "Maintenance Records" tab lists every job carried out with its record code, type, title, equipment or tank, start and finish, downtime, cost and the person responsible.' },
        ekran: '/bakim',
      },
      {
        baslik: { tr: 'Yeni bakım kaydı açın', en: 'Create a maintenance record' },
        metin: { tr: 'Sağ üstteki "Bakım kaydı" düğmesine basın. Kayıt türünü seçin: Periyodik bakım, Arıza, Kalibrasyon, CIP (yerinde temizlik) ya da Temizlik. Ardından ekipman VEYA tank seçin — birini seçtiğinizde diğeri temizlenir, çünkü bir kayıt yalnızca birine ait olabilir. Başlık alanı zorunludur; ne yapıldığını kısa ve anlaşılır yazın.', en: 'Press "Maintenance record" at the top right. Choose the record type: Preventive maintenance, Breakdown, Calibration, CIP (clean-in-place) or Cleaning. Then select either a piece of equipment OR a tank — choosing one clears the other, because a record can belong to only one of them. The title field is mandatory; describe briefly and clearly what was done.' },
        ekran: '/bakim',
      },
      {
        baslik: { tr: 'CIP ayrıntılarını doldurun', en: 'Fill in the CIP details' },
        metin: { tr: 'Kayıt türü olarak CIP ya da Temizlik seçtiğinizde ek bir bölüm açılır: kullanılan kimyasal (örneğin Kostik %2), sıcaklık ve süre. Bu üç değer temizliğin gerçekten etkili olup olmadığını sonradan değerlendirmenin tek yoludur. Temizlik sonucunu doğruladıysanız "Temizlik doğrulandı" kutusunu işaretleyin.', en: 'Selecting CIP or Cleaning as the record type opens an extra section: the chemical used (for example caustic 2%), the temperature and the duration. Those three values are the only way to judge afterwards whether the clean was actually effective. If you verified the result, tick the "Cleaning verified" box.' },
        ekran: '/bakim',
        ipucu: { tr: '"Temizlik doğrulandı" kutusunu yalnızca gerçekten doğrulama yaptıysanız işaretleyin: bu kutu tankı "steril" olarak kaydeder ve sonraki dolumlarda güvence olarak kabul edilir.', en: 'Only tick "Cleaning verified" if you genuinely verified it: the box records the tank as "sterile" and that is treated as assurance for subsequent fills.' },
      },
      {
        baslik: { tr: 'Tank temizlik durumunun güncellenmesini sağlayın', en: 'Make sure the tank\'s cleaning status updates' },
        metin: { tr: 'Bir CIP/temizlik kaydının tankın temizlik durumunu güncellemesi için üç koşul birlikte gerekir: kayıtta tank seçilmiş olmalı, tür CIP ya da Temizlik olmalı ve "İş tamamlandı" kutusu işaretli olmalı. Bu koşullar sağlandığında tank "Temiz" olur; "Temizlik doğrulandı" da işaretliyse "Steril" olarak kaydedilir ve son temizlik tarihi güncellenir. Böylece Tanklar ekranındaki kirli tank engeli kalkar.', en: 'For a CIP or cleaning record to update a tank\'s cleaning status, three conditions must hold together: a tank must be selected on the record, the type must be CIP or Cleaning, and the "Work completed" box must be ticked. When they are, the tank becomes "Clean" — or "Sterile" if "Cleaning verified" is also ticked — and its last-cleaned date is updated. This is what clears the dirty-tank block on the Tanks screen.' },
        ekran: '/bakim',
      },
      {
        baslik: { tr: 'Duruş, maliyet ve tamamlanma kutusunu doğru kullanın', en: 'Use downtime, cost and the completion box correctly' },
        metin: { tr: 'Duruş (dakika) alanına ekipmanın üretim dışı kaldığı süreyi, Maliyet alanına yedek parça ve servis bedelini yazın; bu iki değer İstatistikler ekranındaki bakım duruşu analizini besler. "İş tamamlandı" kutusu işaretlenmezse — özellikle arıza kayıtlarında — ekipman "arızalı" durumda kalır ve listelerde öyle görünür.', en: 'Put the time the equipment was out of production into the Downtime (min) field and the parts and service charge into the Cost field; both feed the maintenance downtime analysis on the Statistics screen. If the "Work completed" box is left unticked — especially on breakdown records — the equipment stays in "faulty" status and is shown that way in the lists.' },
        ekran: '/bakim',
        ipucu: { tr: 'Arıza devam ediyorsa kutuyu bilinçli olarak işaretlemeyin; ekipmanın arızalı görünmesi bir sonraki vardiyanın o makineyi planlamasını engeller.', en: 'If the breakdown is ongoing, deliberately leave the box unticked; showing the equipment as faulty stops the next shift from planning work on that machine.' },
      },
    ],
    sorular: [
      {
        soru: { tr: 'Bir tankı CIP ile temizlediniz. Kaydın tankın temizlik durumunu güncellemesi için hangi koşullar gerekir?', en: 'You cleaned a tank with CIP. What must be true for the record to update the tank\'s cleaning status?' },
        secenekler: { tr: ['Yalnızca kayıt türünün CIP seçilmesi yeterlidir.', 'Kayıtta tankın seçilmesi, türün CIP/Temizlik olması ve "İş tamamlandı" kutusunun işaretli olması.', 'Kaydın enolog tarafından onaylanması.', 'Tankın önce boşaltılıp devre dışı bırakılması.'], en: ['Selecting CIP as the record type is enough on its own.', 'A tank must be selected on the record, the type must be CIP/Cleaning and the "Work completed" box must be ticked.', 'The record must be approved by the winemaker.', 'The tank must first be emptied and decommissioned.'] },
        dogru: 1,
        aciklama: { tr: 'Üç koşul birlikte sağlandığında tank "Temiz" olur; ayrıca "Temizlik doğrulandı" işaretliyse "Steril" olarak kaydedilir.', en: 'When all three conditions hold the tank becomes "Clean"; if "Cleaning verified" is also ticked it is recorded as "Sterile".' },
      },
      {
        soru: { tr: 'Bir arıza kaydı girdiniz ve "İş tamamlandı" kutusunu işaretlemediniz. Sonuç ne olur?', en: 'You entered a breakdown record and left the "Work completed" box unticked. What is the result?' },
        secenekler: { tr: ['Kayıt hiç oluşmaz.', 'Ekipman "arızalı" durumda kalır ve listelerde öyle görünür.', 'Ekipman otomatik olarak envanterden silinir.', 'Kayıt yalnızca yöneticiye bildirim olarak gider, listeye düşmez.'], en: ['The record is not created at all.', 'The equipment stays in "faulty" status and is shown that way in the lists.', 'The equipment is automatically removed from the inventory.', 'The record only notifies the manager and never appears in the list.'] },
        dogru: 1,
        aciklama: { tr: 'Bu bilinçli bir davranıştır: iş bitmediyse ekipman arızalı görünmeli ki bir sonraki vardiya o makineyi üretime almasın.', en: 'This behaviour is deliberate: while the job is unfinished the equipment must read as faulty so the next shift does not schedule production on it.' },
      },
      {
        soru: { tr: 'Yaklaşan bakımlar kartında bir satır amber ve "gün gecikti" yazıyor. Ne yapılmalıdır?', en: 'A row in the upcoming-maintenance card is amber and says "days overdue". What should be done?' },
        secenekler: { tr: ['Satırı listeden kaldırmak.', 'İlgili ekipman için bakım kaydı girmek; kayıt tamamlandığında sonraki bakım tarihi ileri alınır.', 'Ekipmanın bakım periyodunu silmek.', 'Beklemek; sistem tarihi kendiliğinden ileri alır.'], en: ['Remove the row from the list.', 'Enter a maintenance record for that equipment; completing it pushes the next maintenance date forward.', 'Delete the equipment\'s maintenance interval.', 'Wait; the system will move the date forward by itself.'] },
        dogru: 1,
        aciklama: { tr: 'Gecikme yalnızca yapılan iş kaydedilince kapanır. Periyodu silmek uyarıyı susturur ama bakım borcunu ortadan kaldırmaz.', en: 'An overdue item only clears once the work is recorded. Deleting the interval silences the warning but does not discharge the maintenance debt.' },
      },
    ],
  },
  {
    kod: 'rapor-istatistik-yedekleme',
    baslik: { tr: 'Raporlar, İstatistikler ve Yedekleme', en: 'Reports, Statistics and Backup' },
    ozet: { tr: 'Maliyet raporları ve dışa aktarma, eğilim analizleri, Kontrol Paneli ile İstatistikler farkı ve yedek alma sorumluluğu.', en: 'Cost reports and exports, trend analysis, the difference between the Dashboard and Statistics, and the responsibility that comes with backups.' },
    roller: ['isletme_yoneticisi', 'muhasebe', 'satis_personeli', 'denetci', 'enolog', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Raporlar ekranındaki özeti okuyun', en: 'Read the summary on the Reports screen' },
        metin: { tr: 'Raporlar ekranı üstte toplam üzüm kabulü, kabul sayısı, aktif parti sayısı, şişelenen adet ve verim göstergelerini verir. Altında çeşit bazlı ve aylık üzüm kabul grafikleri, en altta ise parti bazlı maliyet tablosu bulunur: parti, ad, rekolte, hacim, şişe adedi, toplam maliyet, TRY/L ve TRY/şişe.', en: 'The Reports screen opens with headline figures: total grape intake, intake count, active lots, bottles produced and yield. Below them are grape-intake charts by variety and by month, and at the bottom the lot-based cost table: lot, name, vintage, volume, bottles, total cost, TRY/L and TRY/bottle.' },
        ekran: '/raporlar',
      },
      {
        baslik: { tr: 'Rapor dışa aktarın', en: 'Export a report' },
        metin: { tr: 'Sayfanın "Dışa aktarma" bölümünde beş rapor listelenir: üzüm kabul/üretim, fermantasyon, laboratuvar analizleri, parti bazlı maliyet ve stok durumu. Her raporun yanındaki Excel, CSV ve PDF düğmelerinden birine basarak dosyayı indirin. Dışa aktarma ayrı bir yetki ister; yetkiniz yoksa bu bölüm yerine bir bilgi mesajı görürsünüz.', en: 'The "Export" section of the page lists five reports: grape intake/production, fermentation, laboratory analyses, lot-based cost and stock status. Press the Excel, CSV or PDF button beside a report to download the file. Exporting requires a separate permission; without it you see an information message instead of the section.' },
        ekran: '/raporlar',
        ipucu: { tr: 'Her indirme denetim günlüğüne yazılır. Dışa aktarılan dosya şaraphane verisini makineden çıkarır; nereye kaydettiğinize ve kiminle paylaştığınıza dikkat edin.', en: 'Every download is written to the audit log. An exported file takes winery data off this machine, so mind where you save it and who you share it with.' },
      },
      {
        baslik: { tr: 'İstatistikler ile Kontrol Panelini ayırt edin', en: 'Tell Statistics and the Dashboard apart' },
        metin: { tr: 'Kontrol Paneli "şu anda ne oluyor" sorusunu, İstatistikler ise "işletme nasıl gidiyor" sorusunu yanıtlar. İstatistikler ekranında parsel bazlı verim, üzümden şişeye kayıp zinciri, fermantasyon süreleri, spesifikasyon dışı analiz oranı, şişeleme verimi, fıçı kullanımı, stok devri ve bakım duruşları yer alır. Üstteki yıl seçicisi rekolte bazlı sekmelerde dönem karşılaştırması yapmanızı sağlar.', en: 'The Dashboard answers "what is happening right now"; Statistics answers "how is the business doing". The Statistics screen covers yield per parcel, the grape-to-bottle loss chain, fermentation durations, the share of out-of-spec analyses, bottling yield, barrel utilisation, stock turnover and maintenance downtime. The year selector at the top lets you compare periods on the vintage-based tabs.' },
        ekran: '/istatistikler',
      },
      {
        baslik: { tr: 'Yetkiye göre değişen sekmeleri anlayın', en: 'Understand why the tabs differ by role' },
        metin: { tr: 'İstatistikler ekranındaki her sekme kendi yetkisiyle korunur ve yetkiniz olmayan sekme hiç istenmez. Bu yüzden satış personeli Laboratuvar sekmesini, depo personeli maliyet içeren görünümleri göremez. Tek bir uç nokta kullanılsaydı rapor yetkisi olan herkes laboratuvar ve maliyet verisini de görürdü; ayrım bilinçlidir.', en: 'Each tab on the Statistics screen is protected by its own permission, and a tab you are not entitled to is never even requested. That is why a sales representative does not see the Laboratory tab and a warehouse clerk does not see cost views. Had a single endpoint been used, anyone with report access would also see lab and cost data — the separation is deliberate.' },
        ekran: '/istatistikler',
      },
      {
        baslik: { tr: 'Yedek alın', en: 'Create a backup' },
        metin: { tr: 'Yedekleme ekranındaki "Yedek al" düğmesi veritabanının tutarlı bir kopyasını üretir; "Belgeleri de arşivle" kutusunu işaretlerseniz yüklenen belgeler de arşivlenir. Üstteki kartlar yedek sayısını, toplam boyutu, diskteki boş alanı ve yedek klasörünün konumunu gösterir. "Eski yedekleri temizle" düğmesi saklama süresi dolmuş dosyaları siler. Bu ekran yedek yönetimi yetkisi ister.', en: 'The "Create backup" button on the Backup screen produces a consistent copy of the database; tick "Archive documents as well" to include uploaded documents. The cards at the top show the backup count, total size, free disk space and the location of the backup folder. "Purge old backups" removes files past their retention period. This screen requires the backup management permission.' },
        ekran: '/yedekleme',
        ipucu: { tr: 'Yedekleri düzenli olarak farklı bir fiziksel ortama kopyalayın. Aynı diskteki yedek, disk arızasında verinin kendisiyle birlikte kaybolur.', en: 'Copy your backups to a different physical medium on a regular basis. A backup on the same disk is lost together with the data when that disk fails.' },
      },
      {
        baslik: { tr: 'Yedek dosyasının neden hassas olduğunu bilin', en: 'Know why a backup file is sensitive' },
        metin: { tr: 'Yedek dosyası tüm veritabanının kopyasıdır: parola özetleri, şifreli API anahtarları ve denetim günlüğü dahil. Bu yüzden yedek almak ile yedeği makine dışına indirmek ayrı yetkilerdir ve indirme yalnızca sistem yöneticisine açıktır; her indirme denetim günlüğüne yazılır. Geri yükleme uygulama içinden yapılamaz — bilinçli bir güvenlik kararıdır ve yordamı ayrıca belgelenmiştir.', en: 'A backup file is a copy of the entire database, including password hashes, encrypted API keys and the audit log. That is why creating a backup and downloading one off the machine are separate permissions, with downloading reserved for the system administrator and every download written to the audit log. Restoring cannot be done from inside the application — a deliberate security decision, with the procedure documented separately.' },
        ekran: '/yedekleme',
      },
    ],
    sorular: [
      {
        soru: { tr: 'Kontrol Paneli ile İstatistikler ekranı arasındaki temel fark nedir?', en: 'What is the essential difference between the Dashboard and the Statistics screen?' },
        secenekler: { tr: ['Kontrol Paneli yalnızca yöneticilere açıktır.', 'Kontrol Paneli anlık durumu; İstatistikler verim, kayıp, süre ve dönem karşılaştırması gibi eğilimleri gösterir.', 'İstatistikler yalnızca dışa aktarma amacıyla kullanılır.', 'İkisi aynı veriyi yalnızca farklı renklerle gösterir.'], en: ['The Dashboard is only available to managers.', 'The Dashboard shows the live picture; Statistics shows trends such as yield, loss, duration and period comparison.', 'Statistics exists purely for exporting.', 'They show the same data in different colours.'] },
        dogru: 1,
        aciklama: { tr: 'Kontrol Paneli "şu anda ne oluyor", İstatistikler "işletme nasıl gidiyor" sorusunu yanıtlar. İkisi birbirinin yerine geçmez.', en: 'The Dashboard answers "what is happening now", Statistics answers "how is the business doing". Neither replaces the other.' },
      },
      {
        soru: { tr: 'Satış personeli İstatistikler ekranını açtığında laboratuvar ve maliyet içeren sekmeleri görmüyor. Bunun nedeni nedir?', en: 'A sales representative opens Statistics and cannot see the laboratory or cost tabs. Why?' },
        secenekler: { tr: ['Bu sekmeler yalnızca masaüstü sürümde vardır.', 'Her sekme kendi yetkisiyle korunur; yetkisi olmayan sekme hiç istenmez ve gösterilmez.', 'Veriler o dönem için henüz hesaplanmamıştır.', 'Sekmeler seçilen dile göre değişir.'], en: ['Those tabs only exist in the desktop build.', 'Each tab is protected by its own permission; a tab the user lacks rights to is never requested or shown.', 'The data has not been calculated for that period yet.', 'The tabs vary with the selected language.'] },
        dogru: 1,
        aciklama: { tr: 'Sekme bazlı yetkilendirme bilinçli bir tasarımdır: rapor okuma yetkisi tek başına maliyet ya da laboratuvar verisine erişim vermez.', en: 'Per-tab authorisation is by design: holding the report read permission alone does not grant access to cost or laboratory data.' },
      },
      {
        soru: { tr: 'Yedek dosyasını indirmek neden ayrı bir yetkidir?', en: 'Why is downloading a backup file a separate permission?' },
        secenekler: { tr: ['Dosya çok büyük olduğu ve ağı yorduğu için.', 'Yedek tüm veritabanının kopyasıdır: parola özetleri, şifreli API anahtarları ve denetim günlüğü içerir; makine dışına çıkarmak ayrı bir sorumluluktur.', 'İndirme işlemi sunucuyu geçici olarak durdurduğu için.', 'Yedekler yalnızca PDF biçiminde indirilebildiği için.'], en: ['The file is large and strains the network.', 'A backup is a copy of the entire database — password hashes, encrypted API keys and the audit log — so taking it off the machine is a separate responsibility.', 'Downloading briefly stops the server.', 'Backups can only be downloaded as PDF.'] },
        dogru: 1,
        aciklama: { tr: 'Yedek ALMAK işletme sorumluluğudur; yedeği makine dışına ÇIKARMAK sistem yöneticisinin sorumluluğudur. Her indirme denetim günlüğüne yazılır.', en: 'Creating a backup is an operational responsibility; taking one off the machine is the system administrator\'s. Every download is written to the audit log.' },
      },
    ],
  },
  {
    kod: 'yapay-zeka-guvenli-kullanim',
    baslik: { tr: 'Yapay Zekâ Merkezi ve Güvenli Kullanım', en: 'The AI Workbench and Using It Safely' },
    ozet: { tr: 'Sağlayıcı ve görev seçimi, veri bağlamı, harici paylaşım öncesi kapsam onayı, hazır sayısal analizler ve AI terminalinin güvenlik akışı.', en: 'Choosing a provider and task, setting the data context, approving the scope before any external sharing, the ready-made numerical analyses and the AI terminal\'s safety flow.' },
    roller: ['enolog', 'bagcilik_uzmani', 'laboratuvar_teknisyeni', 'mahzen_sorumlusu', 'uretim_operatoru', 'siseleme_personeli', 'depo_sevkiyat', 'satis_personeli', 'muhasebe', 'isletme_yoneticisi', 'sistem_yoneticisi'],
    sureDk: 12,
    adimlar: [
      {
        baslik: { tr: 'Sağlayıcı ve görev türünü seçin', en: 'Choose the provider and task type' },
        metin: { tr: 'Yapay Zekâ Merkezi\'nin sol panelindeki "Sağlayıcı ve görev" kartından sağlayıcıyı seçin. Kilit simgesi taşıyan sağlayıcı yereldir (LM Studio); Claude ve NVIDIA Build bulut sağlayıcılarıdır. "Otomatik (göreve göre)" seçeneği görev türüne göre uygun sağlayıcıyı seçer. Görev türü listesi Şaraphane danışmanı, Veri analisti, Rapor yazarı, Kalite kontrol ve diğerlerini içerir; seçim modelin bakış açısını belirler.', en: 'Pick a provider in the "Provider and task" card in the left panel of the AI Workbench. A provider with a padlock icon is local (LM Studio); Claude and NVIDIA Build are cloud providers. "Automatic (by task)" picks a suitable provider for the task type. The task list includes Winery consultant, Data analyst, Report writer, Quality control and others; your choice sets the model\'s frame of reference.' },
        ekran: '/yapay-zeka',
      },
      {
        baslik: { tr: 'Gizlilik uyarısını okuyun', en: 'Read the privacy notice' },
        metin: { tr: 'Sağlayıcıyı seçtiğinizde kartın altında renkli bir uyarı belirir. Yeşil kutu, yerel modelde verinin bu bilgisayardan çıkmadığını söyler. Amber kutu ise seçtiğiniz sağlayıcının harici bir bulut servisi olduğunu ve şaraphane verisi gönderilmeden önce onayınızın isteneceğini belirtir. Hassas analizlerde yerel modeli tercih edin.', en: 'Once you select a provider, a coloured notice appears under the card. A green box tells you the local model keeps data on this computer. An amber box tells you the provider is an external cloud service and that your approval will be requested before any winery data is sent. For sensitive analyses, prefer the local model.' },
        ekran: '/yapay-zeka',
      },
      {
        baslik: { tr: 'Veri bağlamını kurun', en: 'Set the data context' },
        metin: { tr: '"Veri bağlamı" kartından modele hangi kayıtların verileceğini siz belirlersiniz. Parti listesinden bir ya da birden çok parti seçebilir, "Genel işletme durumunu ekle" ile pano özetini ekleyebilir, "Doküman aramasını kullan (RAG)" ile yerel belgelerden alıntı çektirebilirsiniz. Hiçbirini seçmezseniz model yalnızca yazdığınız metni görür.', en: 'The "Data context" card is where you decide which records the model is given. You can select one or more lots from the list, add the dashboard summary with "Include overall operations status", and pull quotes from local documents with "Use document search (RAG)". If you select none of these, the model sees only the text you typed.' },
        ekran: '/yapay-zeka',
        ipucu: { tr: 'Bağlamı ihtiyaç kadar dar tutun. Gereksiz parti eklemek hem yanıtı bulanıklaştırır hem de harici sağlayıcıda gönderilen veri miktarını büyütür.', en: 'Keep the context as narrow as the question requires. Extra lots blur the answer and, with an external provider, enlarge the amount of data sent.' },
      },
      {
        baslik: { tr: 'Harici paylaşımı bilinçli onaylayın', en: 'Approve external sharing deliberately' },
        metin: { tr: 'Harici bir sağlayıcı seçtiyseniz ve bağlama parti ya da pano verisi eklediyseniz, "Gönder" düğmesi mesajı doğrudan göndermez. Önce "Gönderilecek veri kapsamı" penceresi açılır: hangi tür, hangi kod, hangi ad ve hangi alanların gideceğini satır satır listeler ve yaklaşık karakter sayısını verir. "Onaylıyorum, gönder" demeden hiçbir kayıt dışarı çıkmaz; "İptal" ile vazgeçebilirsiniz.', en: 'If you chose an external provider and added lot or dashboard data to the context, the "Send" button does not send straight away. A "Data scope to be sent" dialog opens first, listing row by row which type, code, name and fields will leave the machine, together with an approximate character count. Nothing is sent until you press "I approve, send"; "Cancel" backs out.' },
        ekran: '/yapay-zeka',
        ipucu: { tr: 'Kapsam penceresini okumadan onaylamayın. Bu pencere, şaraphane verisinin makineden çıkışındaki son ve tek duraktır.', en: 'Never approve the scope dialog without reading it. It is the last and only checkpoint before winery data leaves this machine.' },
      },
      {
        baslik: { tr: 'Hazır analizleri kullanın', en: 'Use the ready-made analyses' },
        metin: { tr: 'Sol paneldeki "Hazır analizler" kartında üç düğme vardır: Stok tükenme tahmini, Bakım zamanı tahmini ve Doğal dil raporu. İlk ikisi tamamen yerel sayısal çekirdekle çalışır ve sağlayıcı kapalıyken de sonuç üretir. Sonuç kartında bir seviye rozeti, başlık, özet ve varsa model yorumu görünür.', en: 'The "Ready-made analyses" card in the left panel has three buttons: Stock depletion forecast, Maintenance due forecast and Natural language report. The first two run entirely on the local numerical core and produce results even with every provider disabled. The result card shows a severity badge, a title, a summary and, where available, a model commentary.' },
        ekran: '/yapay-zeka',
      },
      {
        baslik: { tr: 'Sağlayıcı ayarlarını ve maliyeti izleyin', en: 'Configure providers and watch the cost' },
        metin: { tr: 'Ayarlar ekranında her sağlayıcı için sunucu adresi, varsayılan model, zaman aşımı, yeniden deneme ve token maliyetleri tanımlanır; "Bağlantıyı test et" ve "Model listesini yenile" düğmeleriyle durum doğrulanır. API anahtarları şifreli saklanır ve ekranda yalnızca maskeli görünür. Yapay Zekâ Merkezi\'ndeki "Kullanım (30 gün)" kartı istek sayısını, token miktarını ve tahmini maliyeti gösterir.', en: 'On the Settings screen each provider gets a server address, default model, timeout, retry count and token pricing; "Test connection" and "Refresh model list" confirm its state. API keys are stored encrypted and only ever shown masked on screen. The "Usage (30 days)" card in the AI Workbench reports request counts, token volumes and the estimated cost.' },
        ekran: '/ayarlar',
      },
      {
        baslik: { tr: 'AI Terminalinin güvenlik akışını izleyin', en: 'Follow the AI terminal\'s safety flow' },
        metin: { tr: 'AI Terminali yalnızca geliştirme yetkisi olan kullanıcılara açıktır ve sabit bir sıra izler: plan oluştur → onayla (bu adımda git kontrol noktası açılır) → komutları çalıştır → lint ve testlerle doğrula → gerekirse geri al. Güvenlik kartı çalışma alanını, izinli araçları ve engellenen işlemleri listeler; alttaki kutuya bir komut yazıp "Denetle" diyerek çalıştırmadan önce izinli olup olmadığını görebilirsiniz.', en: 'The AI terminal is open only to users with the development permission and follows a fixed sequence: create plan → approve (a git checkpoint is created at this step) → run the commands → verify with lint and tests → roll back if needed. The security card lists the workspace, the allowed tools and the blocked operations; type a command into the box below and press "Check" to see whether it is permitted before anything runs.' },
        ekran: '/ai-terminal',
        ipucu: { tr: 'Onay adımı git kontrol noktası oluşturduğu için geri alma mümkündür. Onaysız çalıştırma yoktur; "engellendi" işaretli bir görev onaylansa bile çalıştırılamaz.', en: 'Because the approval step creates a git checkpoint, rolling back is possible. Nothing runs without approval, and a task flagged as "blocked" cannot be run even if approved.' },
      },
    ],
    sorular: [
      {
        soru: { tr: 'Sağlayıcı olarak bulut tabanlı bir modeli seçtiniz ve veri bağlamına iki parti eklediniz. "Gönder" düğmesine bastığınızda ne olur?', en: 'You chose a cloud provider and added two lots to the data context. What happens when you press "Send"?' },
        secenekler: { tr: ['Mesaj ve parti verisi doğrudan gönderilir.', 'Önce "Gönderilecek veri kapsamı" penceresi açılır; tabloyu görüp onaylamadan hiçbir kayıt dışarı çıkmaz.', 'İstek reddedilir; bulut sağlayıcıya parti verisi hiç gönderilemez.', 'Veri otomatik olarak anonimleştirilip sessizce gönderilir.'], en: ['The message and the lot data are sent immediately.', 'A "Data scope to be sent" dialog opens first; nothing leaves until you review the table and approve.', 'The request is refused; lot data can never be sent to a cloud provider.', 'The data is anonymised automatically and sent silently.'] },
        dogru: 1,
        aciklama: { tr: 'Kapsam onayı harici paylaşımdaki tek kapıdır. Yerel sağlayıcıda ya da bağlama veri eklenmediğinde bu pencere açılmaz, çünkü dışarı çıkacak şaraphane kaydı yoktur.', en: 'Scope approval is the single gate for external sharing. With a local provider, or when no data was added to the context, the dialog does not appear — there is no winery record to send.' },
      },
      {
        soru: { tr: 'Yerel model kapalıyken "Stok tükenme tahmini" analizini çalıştırdınız. Ne beklersiniz?', en: 'You run the "Stock depletion forecast" while the local model is switched off. What should you expect?' },
        secenekler: { tr: ['Uygulama hata verip kapanır.', 'Analiz yine çalışır: sayısal çekirdek dil modelinden bağımsızdır; yalnızca metin yorumu üretilmeyebilir.', 'Analiz sessizce boş sonuç döner.', 'Sistem otomatik olarak bulut sağlayıcıya geçer ve veriyi onaysız gönderir.'], en: ['The application errors out and closes.', 'The analysis still runs: the numerical core is independent of any language model; only the written commentary may be missing.', 'The analysis silently returns an empty result.', 'The system switches to a cloud provider and sends the data without asking.'] },
        dogru: 1,
        aciklama: { tr: 'Fermantasyon tahmini, anomali tespiti, kalite puanı, risk değerlendirmesi, stok ve bakım tahmini sağlayıcı kapalıyken de çalışacak şekilde tasarlanmıştır.', en: 'Fermentation prediction, anomaly detection, quality scoring, risk assessment and the stock and maintenance forecasts are all designed to work with every provider disabled.' },
      },
      {
        soru: { tr: 'AI Terminalinde bir görevin doğru sırası hangisidir?', en: 'What is the correct sequence for a task in the AI terminal?' },
        secenekler: { tr: ['Çalıştır → plan oluştur → onayla → test et', 'Plan oluştur → onayla (git kontrol noktası) → komutları çalıştır → lint ve testlerle doğrula → gerekirse geri al', 'Onayla → geri al → plan oluştur → çalıştır', 'Plan oluştur → çalıştır → sonradan onayla'], en: ['Run → create plan → approve → test', 'Create plan → approve (git checkpoint) → run the commands → verify with lint and tests → roll back if needed', 'Approve → roll back → create plan → run', 'Create plan → run → approve afterwards'] },
        dogru: 1,
        aciklama: { tr: 'Onay adımı kontrol noktasını oluşturduğu için geri almayı mümkün kılar; bu yüzden çalıştırma her zaman onaydan sonra gelir.', en: 'The approval step creates the checkpoint that makes rolling back possible, which is why execution always comes after approval.' },
      },
    ],
  },
]
