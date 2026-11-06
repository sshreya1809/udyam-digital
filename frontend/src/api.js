export async function api(path, body) {
  const init = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch("/api/" + path, init);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

export const inr = (n) => "Rs " + Number(n).toLocaleString("en-IN");

export const SLOTS = {
  gst_certificate: "GST certificate",
  udyam_certificate: "Udyam certificate",
  signatory_id: "Signatory ID",
  address_proof: "Address proof",
};

export function toBase64(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result.split(",")[1]);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}
