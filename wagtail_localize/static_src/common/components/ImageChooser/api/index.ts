export interface ImageAPI {
    id: number;
    title: string;
    thumbnail: {
        url: string;
        width: number;
        height: number;
    };
}

const isImageAPI = (value: unknown): value is ImageAPI => {
    if (typeof value !== 'object' || value === null) {
        return false;
    }

    const image = value as Partial<ImageAPI>;
    const { thumbnail } = image;

    return (
        typeof image.id === 'number' &&
        typeof image.title === 'string' &&
        typeof thumbnail === 'object' &&
        thumbnail !== null &&
        typeof thumbnail.url === 'string' &&
        typeof thumbnail.width === 'number' &&
        typeof thumbnail.height === 'number'
    );
};

export const fetchImageInfo = async (
    adminBaseUrl: string,
    imageId: number
): Promise<ImageAPI | null> => {
    try {
        const response = await fetch(
            `${adminBaseUrl}api/main/images/${imageId}/`
        );

        if (!response.ok) {
            return null;
        }

        const image = await response.json();
        return isImageAPI(image) ? image : null;
    } catch {
        return null;
    }
};
