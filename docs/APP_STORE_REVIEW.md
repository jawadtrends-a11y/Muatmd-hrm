# ملفّ مراجعة App Store — معتمد Muatmd HR

⚠️⚠️ **رُفضت النسخة السابقة بالمادّة ٣٫٢** — فُهم التطبيق **تطبيقًا داخليًّا
لشركةٍ واحدة**. وهو في الحقيقة **منصّة SaaS تُباع بالاشتراك لشركاتٍ متعدّدة**.

## App Review Notes (تُلصق في App Store Connect)

Muatmd HR is a multi-tenant HR SaaS platform sold by subscription to
businesses in Saudi Arabia. It is NOT an internal app for a single company.

Any company can sign up at https://muatmd.sa and receive its own isolated
tenant. Each tenant has its own employees, payroll, attendance and policies;
tenants cannot see each other's data (enforced at the database level with
PostgreSQL row-level security).

The app is the employee-facing companion to the web platform: employees of
ANY subscribing company use it to clock in and out, request leave, view
payslips, and approve their team's requests.

DEMO ACCOUNT (a dedicated demo tenant, separate from real customers):
  URL      : https://hr.muatmd.sa
  Username : appreview
  Password : Review@2026

This demo tenant contains 5 sample employees, completely isolated from our
paying customers' data — which itself demonstrates the multi-tenant model.

Public product page (Arabic): https://muatmd.sa
Compliance: GOSI, Mudad and WPS per Saudi labour regulations.

## وصف المتجر (عربيّ)

**معتمد — نظام الموارد البشرية**

منصّةٌ سحابيّةٌ لإدارة الموارد البشرية، تشترك فيها الشركات بالباقة التي تناسب
حجمها. ولكلّ شركةٍ حسابها المستقلّ ببياناتها وسياساتها.

**للموظّف:** البصمة من الجوّال بتحديد الموقع · طلب الإجازات والسُّلف ومتابعتها ·
قسائم الرواتب وتحميلها PDF · الملفّ الشخصيّ والوثائق.

**للمدير:** اعتماد طلبات الفريق من الجوّال · متابعة حضور المرؤوسين · ملفّات
الفريق وتاريخهم الوظيفيّ.

**متوافقٌ مع الأنظمة السعوديّة:** التأمينات الاجتماعية · مدد · حماية الأجور ·
ونظام العمل السعوديّ في الإجازات ونهاية الخدمة.

⚠️ **يتطلّب اشتراك شركتك في منصّة معتمد.** للاشتراك: muatmd.sa

## وصف المتجر (إنجليزيّ)

**Muatmd HR — Human Resources**

A cloud HR platform that companies subscribe to. Each company gets its own
isolated workspace with its own employees, policies and payroll.

**For employees:** geo-verified clock in/out · leave and advance requests ·
payslips as PDF · personal profile and documents.

**For managers:** approve team requests on the go · track team attendance ·
view team profiles and job history.

**Built for Saudi regulations:** GOSI · Mudad · WPS · and Saudi Labour Law.

⚠️ Requires an active subscription for your company. Sign up at muatmd.sa

## ما يجب أن تُظهره لقطات الشاشة

⚠️ **اللقطات جزءٌ من الإثبات** — فالمراجع يقرؤها قبل النصّ:
1. **شاشة الدخول وفيها اسم الشركة ظاهرًا** — فيُفهم أنّ لكلٍّ حسابه
2. البصمة بالموقع
3. قائمة الطلبات
4. قسيمة الراتب
5. اعتماد طلبات الفريق

⚠️ **ولا تُظهر أيّ لقطةٍ بيانات عميلٍ حقيقيّ** — تُلتقط من حساب المراجعة.

## قائمة التحقّق قبل الرفع

- [ ] مفتاح APNs (يحتاج دخولًا لحساب Apple — عطّلته خدمةُ Apple)
- [ ] إعادة بناء iOS بعد إضافة المفتاح
- [ ] اللقطات من حساب appreview
- [ ] **سياسة الخصوصية** على muatmd.sa — ⚠️ **شرطٌ لا يُتجاوز**
- [ ] App Review Notes أعلاه في App Store Connect
