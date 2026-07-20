using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class GhostRiggerFacialExportProof
{
    [Serializable]
    public sealed class CharacterAudit
    {
        public string label = "";
        public string assetPath = "";
        public string clipName = "";
        public int hierarchyNodes;
        public int rendererCount;
        public int skinnedRendererCount;
        public int facialCurveBindings;
        public int attachedRigidFacialRenderers;
        public string[] attachedRigidFacialNames = Array.Empty<string>();
        public int unattachedRigidFacialRenderers;
        public string[] unattachedRigidFacialNames = Array.Empty<string>();
        public float maximumFacialTranslationDelta;
        public float maximumFacialRotationDegrees;
        public float maximumRigidFacialDistanceFromHead;
        public string bindImage = "";
        public string animatedImage = "";
        public bool passed;
    }

    [Serializable]
    public sealed class ProofReport
    {
        public string unityVersion = "";
        public bool passed;
        public List<CharacterAudit> characters = new List<CharacterAudit>();
    }

    private sealed class Fixture
    {
        public readonly string Label;
        public readonly string AssetPath;

        public Fixture(string label, string assetPath)
        {
            Label = label;
            AssetPath = assetPath;
        }
    }

    private static readonly Fixture[] Fixtures =
    {
        new Fixture("carth", "Assets/FacialProof/carth/carth_tlknorm.fbx"),
        new Fixture("darth_bandon", "Assets/FacialProof/darth_bandon/darth_bandon_tlknorm.fbx"),
    };

    public static void Run()
    {
        try
        {
            var outputRoot = CommandLineValue("-facialProofOutput");
            if (String.IsNullOrWhiteSpace(outputRoot))
                outputRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "FacialProof"));
            outputRoot = Path.GetFullPath(outputRoot);
            Directory.CreateDirectory(outputRoot);

            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var report = new ProofReport { unityVersion = Application.unityVersion };
            foreach (var fixture in Fixtures)
                report.characters.Add(AuditFixture(fixture, outputRoot));
            report.passed = report.characters.Count == Fixtures.Length
                && report.characters.All(item => item.passed);

            var reportPath = Path.Combine(outputRoot, "unity_facial_export_proof.json");
            File.WriteAllText(reportPath, JsonUtility.ToJson(report, true));
            Debug.Log($"GHOSTRIGGER_FACIAL_EXPORT_PROOF passed={report.passed} output={reportPath}");
            EditorApplication.Exit(report.passed ? 0 : 3);
        }
        catch (Exception exc)
        {
            Debug.LogException(exc);
            EditorApplication.Exit(2);
        }
    }

    private static CharacterAudit AuditFixture(Fixture fixture, string outputRoot)
    {
        AssetDatabase.ImportAsset(fixture.AssetPath, ImportAssetOptions.ForceSynchronousImport);
        var importer = AssetImporter.GetAtPath(fixture.AssetPath) as ModelImporter;
        if (importer == null)
            throw new InvalidOperationException($"Unity did not create a ModelImporter for {fixture.AssetPath}.");
        importer.globalScale = 1.0f;
        importer.useFileScale = true;
        importer.bakeAxisConversion = true;
        importer.importAnimation = true;
        importer.animationType = ModelImporterAnimationType.Generic;
        importer.animationCompression = ModelImporterAnimationCompression.Off;
        importer.resampleCurves = false;
        importer.SaveAndReimport();

        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(fixture.AssetPath);
        if (prefab == null)
            throw new InvalidOperationException($"Unity did not load the FBX prefab {fixture.AssetPath}.");
        var clips = AssetDatabase.LoadAllAssetsAtPath(fixture.AssetPath)
            .OfType<AnimationClip>()
            .Where(clip => !clip.name.StartsWith("__preview__", StringComparison.Ordinal))
            .ToArray();
        var clip = clips.FirstOrDefault(item => NormalizeClipName(item.name) == "tlknorm");
        if (clip == null)
            throw new InvalidOperationException($"{fixture.Label}: Unity did not import the tlknorm clip.");

        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var character = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
        if (character == null)
            throw new InvalidOperationException($"{fixture.Label}: Unity could not instantiate the FBX prefab.");
        character.name = fixture.Label;
        character.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
        foreach (var skin in character.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            skin.updateWhenOffscreen = true;

        var renderers = character.GetComponentsInChildren<Renderer>(true);
        var rigidFacial = renderers
            .Where(renderer => IsRigidFacialName(renderer.gameObject.name))
            .ToArray();
        var attachedRigid = rigidFacial
            .Where(renderer => renderer.gameObject.name.IndexOf("__head", StringComparison.OrdinalIgnoreCase) >= 0)
            .ToArray();
        var unattachedRigid = rigidFacial.Except(attachedRigid).ToArray();
        var facialTransforms = character.GetComponentsInChildren<Transform>(true)
            .Where(transform =>
                transform.name.IndexOf("__head", StringComparison.OrdinalIgnoreCase) >= 0
                && IsFacialControlName(transform.name))
            .ToArray();
        var bindings = AnimationUtility.GetCurveBindings(clip);
        var facialBindings = bindings.Count(binding =>
            binding.path.IndexOf("__head", StringComparison.OrdinalIgnoreCase) >= 0
            && IsFacialControlName(binding.path));

        var basePositions = new Dictionary<Transform, Vector3>();
        var baseRotations = new Dictionary<Transform, Quaternion>();
        clip.SampleAnimation(character, 0.0f);
        foreach (var transform in facialTransforms)
        {
            basePositions[transform] = transform.localPosition;
            baseRotations[transform] = transform.localRotation;
        }

        var maximumTranslation = 0.0f;
        var maximumRotation = 0.0f;
        var maximumRigidDistance = 0.0f;
        for (var index = 0; index <= 12; index++)
        {
            var time = clip.length * index / 12.0f;
            clip.SampleAnimation(character, time);
            foreach (var transform in facialTransforms)
            {
                maximumTranslation = Mathf.Max(
                    maximumTranslation,
                    Vector3.Distance(basePositions[transform], transform.localPosition));
                maximumRotation = Mathf.Max(
                    maximumRotation,
                    Quaternion.Angle(baseRotations[transform], transform.localRotation));
            }
            var headBounds = HeadBounds(character);
            foreach (var renderer in rigidFacial)
            {
                maximumRigidDistance = Mathf.Max(
                    maximumRigidDistance,
                    Vector3.Distance(renderer.bounds.center, headBounds.center));
            }
        }

        AddLighting();
        var bindImage = Path.Combine(outputRoot, fixture.Label + "_tlknorm_bind.png");
        var animatedImage = Path.Combine(outputRoot, fixture.Label + "_tlknorm_animated.png");
        clip.SampleAnimation(character, 0.0f);
        RenderHead(character, bindImage);
        clip.SampleAnimation(character, clip.length * 0.5f);
        RenderHead(character, animatedImage);

        var audit = new CharacterAudit
        {
            label = fixture.Label,
            assetPath = fixture.AssetPath,
            clipName = NormalizeClipName(clip.name),
            hierarchyNodes = character.GetComponentsInChildren<Transform>(true).Length,
            rendererCount = renderers.Length,
            skinnedRendererCount = renderers.Count(renderer => renderer is SkinnedMeshRenderer),
            facialCurveBindings = facialBindings,
            attachedRigidFacialRenderers = attachedRigid.Length,
            attachedRigidFacialNames = attachedRigid.Select(renderer => renderer.gameObject.name).OrderBy(name => name).ToArray(),
            unattachedRigidFacialRenderers = unattachedRigid.Length,
            unattachedRigidFacialNames = unattachedRigid.Select(renderer => renderer.gameObject.name).OrderBy(name => name).ToArray(),
            maximumFacialTranslationDelta = maximumTranslation,
            maximumFacialRotationDegrees = maximumRotation,
            maximumRigidFacialDistanceFromHead = maximumRigidDistance,
            bindImage = bindImage,
            animatedImage = animatedImage,
        };
        audit.passed = audit.clipName == "tlknorm"
            && audit.skinnedRendererCount > 0
            && audit.facialCurveBindings >= 6
            && audit.attachedRigidFacialRenderers >= 4
            && audit.unattachedRigidFacialRenderers == 0
            && (audit.maximumFacialTranslationDelta > 0.000001f || audit.maximumFacialRotationDegrees > 0.001f)
            && audit.maximumRigidFacialDistanceFromHead < 0.5f
            && File.Exists(bindImage)
            && File.Exists(animatedImage);
        UnityEngine.Object.DestroyImmediate(character);
        return audit;
    }

    private static Bounds HeadBounds(GameObject character)
    {
        var candidates = character.GetComponentsInChildren<Renderer>(true)
            .Where(renderer =>
                String.Equals(renderer.gameObject.name, "head", StringComparison.OrdinalIgnoreCase)
                || renderer.gameObject.name.IndexOf("tongue", StringComparison.OrdinalIgnoreCase) >= 0
                || IsRigidFacialName(renderer.gameObject.name))
            .ToArray();
        if (candidates.Length == 0)
            throw new InvalidOperationException("The Unity prefab contains no head renderers.");
        var bounds = candidates[0].bounds;
        for (var index = 1; index < candidates.Length; index++)
            bounds.Encapsulate(candidates[index].bounds);
        return bounds;
    }

    private static void AddLighting()
    {
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.42f, 0.45f, 0.52f);
        RenderSettings.ambientEquatorColor = new Color(0.18f, 0.20f, 0.25f);
        RenderSettings.ambientGroundColor = new Color(0.06f, 0.07f, 0.09f);
        RenderSettings.ambientIntensity = 1.0f;
        var keyObject = new GameObject("Facial Proof Key Light");
        var key = keyObject.AddComponent<Light>();
        key.type = LightType.Directional;
        key.intensity = 1.35f;
        keyObject.transform.rotation = Quaternion.Euler(32.0f, -38.0f, 0.0f);
        var fillObject = new GameObject("Facial Proof Fill Light");
        var fill = fillObject.AddComponent<Light>();
        fill.type = LightType.Directional;
        fill.color = new Color(0.58f, 0.72f, 1.0f);
        fill.intensity = 0.65f;
        fillObject.transform.rotation = Quaternion.Euler(12.0f, 142.0f, 0.0f);
    }

    private static void RenderHead(GameObject character, string outputPath)
    {
        var bounds = HeadBounds(character);
        var cameraObject = new GameObject("Facial Proof Camera");
        var camera = cameraObject.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.035f, 0.045f, 0.065f, 1.0f);
        camera.fieldOfView = 26.0f;
        camera.nearClipPlane = 0.01f;
        camera.farClipPlane = 100.0f;
        var direction = new Vector3(-0.58f, 0.04f, 1.0f).normalized;
        var radius = Mathf.Max(bounds.extents.magnitude, 0.12f);
        var distance = radius / Mathf.Tan(camera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.18f;
        camera.transform.position = bounds.center + direction * distance;
        camera.transform.LookAt(bounds.center, Vector3.up);

        var target = new RenderTexture(960, 960, 24, RenderTextureFormat.ARGB32)
        {
            antiAliasing = 4,
        };
        target.Create();
        camera.targetTexture = target;
        camera.Render();
        var previous = RenderTexture.active;
        RenderTexture.active = target;
        var image = new Texture2D(960, 960, TextureFormat.RGBA32, false, false);
        image.ReadPixels(new Rect(0, 0, 960, 960), 0, 0);
        image.Apply(false, false);
        File.WriteAllBytes(outputPath, image.EncodeToPNG());
        RenderTexture.active = previous;
        camera.targetTexture = null;
        UnityEngine.Object.DestroyImmediate(image);
        target.Release();
        UnityEngine.Object.DestroyImmediate(target);
        UnityEngine.Object.DestroyImmediate(cameraObject);
    }

    private static bool IsRigidFacialName(string name)
    {
        var lower = (name ?? "").ToLowerInvariant();
        return lower.Contains("eye") || lower.Contains("lid") || lower.Contains("teeth") || lower.Contains("tooth");
    }

    private static bool IsFacialControlName(string name)
    {
        var lower = (name ?? "").ToLowerInvariant();
        return lower.Contains("f_") || lower.Contains("talkdummy")
            || lower.Contains("eye") || lower.Contains("lid")
            || lower.Contains("jaw") || lower.Contains("tongue")
            || lower.Contains("teeth") || lower.Contains("tooth");
    }

    private static string NormalizeClipName(string name)
    {
        return (name ?? "").TrimStart('|').ToLowerInvariant();
    }

    private static string CommandLineValue(string key)
    {
        var args = Environment.GetCommandLineArgs();
        for (var index = 0; index + 1 < args.Length; index++)
        {
            if (String.Equals(args[index], key, StringComparison.OrdinalIgnoreCase))
                return args[index + 1];
        }
        return "";
    }
}
