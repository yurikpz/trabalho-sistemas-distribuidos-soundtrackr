// RENOMEIA LISTA
async function renameList(listId) {
    const newName = prompt("Novo nome da lista:");
    if (!newName) return;

    const res = await fetch("/lists/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: listId, name: newName })
    });

    if (res.ok) {
        alert(" Lista renomeada");
        location.reload();
    } else {
        alert("Erro ao renomear lista");
    }
}

// EXCLUI LISTA
async function deleteList(listId) {
    if (!confirm("Excluir esta lista?")) return;

    const res = await fetch("/lists/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: listId })
    });

    if (res.ok) {
        alert("Lista apagada");
        window.location = "/perfil";
    } else {
        alert("Erro ao excluir lista");
    }
}

// REMOVE ITEM DA LISTA
async function removeItemFromList(listId, trackId) {
    const res = await fetch("/lists/remove_item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ list_id: listId, trackId })
    });

    if (res.ok) {
        location.reload();
    } else {
        alert("Erro ao remover item");
    }
}
