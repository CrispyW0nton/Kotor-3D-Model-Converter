// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System.Collections.ObjectModel;
using System.Linq;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Models.TreeDataGrid;
using Avalonia.Controls.Primitives;
using Avalonia.Media;
using DynamicData;
using Kotor.NET.ResourceContainers;
using ReactiveUI;

namespace Toolset.Controls
{
    public partial class ResourceContainerDataGrid : ContentControl
    {
        public static readonly StyledProperty<IResourceContainer> ResourceContainerProperty =
            AvaloniaProperty.Register<ResourceContainerDataGrid, IResourceContainer>(nameof(ResourceContainer));

        public IResourceContainer ResourceContainer
        {
            get => GetValue(ResourceContainerProperty);
            set => SetValue(ResourceContainerProperty, value);
        }

        public ResourceContainerDataGrid()
        {
            InitializeComponent();
        }

        protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
        {
            base.OnPropertyChanged(change);

            if (change.Property ==  ResourceContainerProperty && ResourceContainer != null)
            {
                DataContext = new ResourceContainerDataGridVM(ResourceContainer);
            }
        }
    }

    public class ResourceContainerDataGridVM : ReactiveObject
    {
        private IResourceContainer _resourceContainer;
        private ObservableCollection<ResourceItem> _items;

        public ResourceContainerDataGridVM(IResourceContainer resourceContainer)
        {
            _resourceContainer = resourceContainer;

            var items = new ObservableCollection<ResourceItem>();
            var all = _resourceContainer.All().ToList();
            var types = all.Select(x => x.ResourceType).Distinct();
            foreach (var type in types)
            {
                var typeItem = new ResourceItem { ResRef = type.Extension.ToUpper() };
                var references = all.Where(x => x.ResourceType == type);

                typeItem.Children.AddRange(references.Select(x => new ResourceItem
                {
                    ResRef = x.ResRef.Get(),
                    ResourceType = x.ResourceType.Extension.ToUpper(),
                }));

                items.Add(typeItem);
            }
            _items = items;

            //

            Source = new HierarchicalTreeDataGridSource<ResourceItem>(_items)
            {
                Columns =
                {
                    new HierarchicalExpanderColumn<ResourceItem>
                    (
                        new TextColumn<ResourceItem, string>("ResRef", x => x.ResRef),
                        x => x.Children
                    ),
                    new TextColumn<ResourceItem, string>("Type", x => x.ResourceType),
                },
            };
        }

        public HierarchicalTreeDataGridSource<ResourceItem> Source { get; }
    }

    public class ResourceItem
    {
        public string? ResRef { get; set; }
        public string? ResourceType { get; set; }
        public ObservableCollection<ResourceItem> Children { get; } = new();
    }
}
