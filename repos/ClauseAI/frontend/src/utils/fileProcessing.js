export function getFileType(file) {
    const extension = file.name.split('.').pop().toLowerCase();
    const typeMap = {
        'pdf': 'pdf',
        'docx': 'docx',
        'txt': 'txt'
    };
    return typeMap[extension] || null;
}

export function formatFileSize(bytes) {
    const megabytes = bytes / (1024 * 1024);
    return `${megabytes.toFixed(2)} MB`;
}

export function calculateWordCount(text) {
    return text.split(/\s+/).filter(Boolean).length;
}
