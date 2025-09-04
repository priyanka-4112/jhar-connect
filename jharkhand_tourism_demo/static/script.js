async function sendMessage() {
  let msg = document.getElementById("userInput").value;
  let res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: msg })
  });
  let data = await res.json();
  document.getElementById("chatResponse").innerText = data.response;
}
