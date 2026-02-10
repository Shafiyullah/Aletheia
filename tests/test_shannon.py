import asyncio
from core.shannon import scan_code_for_sinks, verify_vulnerability, patch_vulnerability

async def test_shannon():
    print("--- Testing Shannon Vulnerability Finder ---\n")
    
    # 1. Test Tracer
    print("[1] Running AST Tracer...")
    vulnerable_code = """
import os
user_input = input("Enter command: ")
os.system(user_input)
    """
    sinks = scan_code_for_sinks(vulnerable_code)
    print(f"Sinks Found: {sinks}")
    
    if len(sinks) > 0 and sinks[0]['sink'] == 'os.system':
        print("PASS: Tracer identified 'os.system'.\n")
    else:
        print("FAIL: Tracer failed to identify sink.\n")
        return

    # 2. Test Verification (Taint Analysis)
    print("[2] Verifying Vulnerability with Gemini...")
    sink = sinks[0]
    is_vuln, exploit = await verify_vulnerability(vulnerable_code, sink['sink'], sink['args'])
    
    print(f"Is Vulnerable: {is_vuln}")
    print(f"Exploit Payload: {exploit}")
    
    if is_vuln:
        print("PASS: Gemini correctly identified the vulnerability.\n")
    else:
        print("FAIL: Gemini failed to identify obvious vulnerability.\n")
        # Don't return, try patching anyway to test the flow

    # 3. Test Patching
    print("[3] Generating Patch...")
    if exploit:
        patch = await patch_vulnerability(vulnerable_code, exploit)
    else:
        # Fallback exploit for testing
        patch = await patch_vulnerability(vulnerable_code, "; rm -rf /")

    print(f"Patched Code:\n{patch}\n")
    
    if "subprocess.run" in patch or "shlex.quote" in patch:
        print("PASS: Patch appears to use safer methods.")
    else:
        print("WARN: Patch might not be optimal, check manually.")

if __name__ == "__main__":
    asyncio.run(test_shannon())
