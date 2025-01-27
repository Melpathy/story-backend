import os
import replicate

# Initialize the Replicate client
replicate_api_key = os.getenv("REPLICATE_API_TOKEN")
if not replicate_api_key:
    raise ValueError("Replicate API key not found. Set the REPLICATE_API_TOKEN environment variable.")

replicate_client = replicate.Client(api_token=replicate_api_key)

def generate_image(prompt):
    """
    Generate an image using Replicate's Stable Diffusion model.
    """
    model = "stability-ai/stable-diffusion"
    version_id = "ac732df83cea7fff18b8472768c88ad041fa750ff76822a1affe01863cbe77e4"  # Verified version ID

    # Call the Replicate API to generate the image
    output = replicate_client.run(
        f"{model}:{version_id}",
        input={"prompt": prompt}
    )

    return output[0]  # Returns the URL of the generated image


# Test the function
if __name__ == "__main__":
    prompt = "A magical forest with a glowing unicorn, children's storybook style"
    try:
        image_url = generate_image(prompt)
        print(f"Generated Image URL: {image_url}")
    except Exception as e:
        print(f"Error: {e}")
